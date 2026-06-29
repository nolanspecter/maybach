"""
FastAPI server with two surface areas:

  POST /orchestrate          — full supervisor graph, returns final result
  POST /orchestrate/stream   — same graph, streams SSE progress events
  POST /agents/{name}        — single worker, bypasses orchestrator

The stream endpoint emits events for every routing decision, agent start,
tool call, and completion so the UI can show a live trace.
"""
import re
import json
import logging
import traceback
from config import load_config

# Must run before agent imports — agents call get_llm() at module level
load_config()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

from tools.workspace_tools import _workspace

import agents.vda as vda_agent
import agents.vswe as vswe_agent
import agents.vpm as vpm_agent
import agents.vds as vds_agent
import orchestrator
from orchestrator import OrchestratorState
from langchain_core.messages import BaseMessage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("maybach")

app = FastAPI(title="Maybach Agent Server", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the shared workspace so users can open/download deliverable files.
# Reachable from the UI via the /api/backend/files/* rewrite.
app.mount("/files", StaticFiles(directory=str(_workspace())), name="files")

WORKER_NODES = {"vDA", "vPM", "vSWE", "vDS"}

# Per-agent summary files (vXX_<hex>.md) are internal, not user deliverables.
_SUMMARY_RE = re.compile(r"^v(?:da|pm|swe|ds)_[0-9a-f]+\.md$", re.IGNORECASE)


def _workspace_snapshot() -> set[str]:
    ws = _workspace()
    return {str(p.relative_to(ws)) for p in ws.rglob("*") if p.is_file()}


def _deliverables(before: set[str]) -> list[dict]:
    """Files created this turn that are user-facing deliverables.

    Excludes internal agent summaries and scratch checkpoints.
    """
    ws = _workspace()
    out = []
    for p in sorted(ws.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ws)
        if ".checkpoints" in rel.parts or _SUMMARY_RE.match(rel.name):
            continue
        if str(rel) in before:
            continue
        out.append({"name": rel.name, "path": str(rel)})
    return out

# Single-session conversation memory — persists across requests until reset
_history: list[BaseMessage] = []


class TaskRequest(BaseModel):
    task: str


class TaskResponse(BaseModel):
    agent: str
    result: str


class OrchestrateResponse(BaseModel):
    agents: list[str]
    result: str
    raw: str
    files: list[dict] = []


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _chunk_text(chunk) -> str:
    """Extract plain text from a streamed model chunk.

    Bedrock Converse yields content as a list of typed blocks; Ollama yields a
    plain string. Normalise both to text so tokens can be streamed to the UI.
    """
    if chunk is None:
        return ""
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(block.get("text", "") if block.get("type", "text") == "text" else "")
        return "".join(parts)
    return ""


@app.get("/health")
def health():
    return {"status": "ok"}


@app.delete("/conversation")
def reset_conversation():
    """Clear the in-memory conversation history."""
    global _history
    _history = []
    log.info("conversation  reset")
    return {"status": "cleared"}


@app.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate_endpoint(req: TaskRequest) -> OrchestrateResponse:
    global _history
    log.info("orchestrate  task=%r  history_len=%d", req.task[:80], len(_history))
    try:
        before = _workspace_snapshot()
        raw, updated = orchestrator.run(req.task, history=_history)
        _history = updated
        all_labels = re.findall(r"\[(\w+)\]", raw)
        agents = list(dict.fromkeys(all_labels)) or ["Maybach"]
        match = re.match(r"^\[(\w+)\]\s*", raw)
        result = raw[match.end():] if match else raw
        files = _deliverables(before)
        log.info("orchestrate  done  agents=%s  files=%d", agents, len(files))
        return OrchestrateResponse(agents=agents, result=result, raw=raw, files=files)
    except Exception as e:
        log.error("orchestrate  error: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/orchestrate/stream")
async def orchestrate_stream(req: TaskRequest):
    global _history
    log.info("stream  task=%r  history_len=%d", req.task[:80], len(_history))
    prior = list(_history)
    before_files = _workspace_snapshot()

    async def generate():
        global _history
        init_state = OrchestratorState(
            messages=prior + [HumanMessage(content=req.task)]
        )
        ai_messages: list[str] = []
        active_agent: str = ""
        seen_agents: list[str] = []
        streamed_text: str = ""

        try:
            async for event in orchestrator.graph.astream_events(
                init_state,
                version="v2",
                config={"recursion_limit": 50},
            ):
                etype = event["event"]
                name  = event.get("name", "")
                data  = event.get("data", {})

                if etype == "on_chain_start":
                    if name == "router":
                        log.info("  → routing")
                        yield _sse({"type": "routing"})
                    elif name in WORKER_NODES:
                        active_agent = name
                        if name not in seen_agents:
                            seen_agents.append(name)
                        log.info("  → agent_start  agent=%s", name)
                        yield _sse({"type": "agent_start", "agent": name})
                    elif name == "summarizer":
                        active_agent = ""
                        log.info("  → summarizing")
                        yield _sse({"type": "summarizing"})
                    elif name == "direct":
                        active_agent = ""
                        log.info("  → direct")
                        yield _sse({"type": "direct"})

                elif etype == "on_chat_model_stream":
                    # Stream the user-facing reply token-by-token. Scoped to the
                    # summarizer (and direct) node so worker-internal model
                    # tokens never leak into the final summary text.
                    node = event.get("metadata", {}).get("langgraph_node", "")
                    if node in ("summarizer", "direct"):
                        token = _chunk_text(data.get("chunk"))
                        if token:
                            streamed_text += token
                            yield _sse({"type": "token", "text": token})

                elif etype == "on_tool_start":
                    raw_input = data.get("input", {})
                    preview = str(raw_input)[:120] if raw_input else ""
                    log.info("  → tool_call  agent=%s  tool=%s", active_agent, name)
                    yield _sse({"type": "tool_call", "agent": active_agent, "tool": name, "preview": preview})

                elif etype == "on_tool_end":
                    log.info("  → tool_done  agent=%s  tool=%s", active_agent, name)
                    yield _sse({"type": "tool_done", "agent": active_agent, "tool": name})

                elif etype == "on_chain_end":
                    output = data.get("output", {})
                    # output may be OrchestratorState (Pydantic) or dict depending on node
                    if hasattr(output, "messages"):
                        out_msgs = output.messages          # Pydantic model
                    elif isinstance(output, dict):
                        out_msgs = output.get("messages", [])
                    else:
                        out_msgs = []

                    if name in WORKER_NODES:
                        file_path = out_msgs[-1].content if out_msgs else ""
                        log.info("  → agent_done  agent=%s  file=%s", name, file_path)
                        yield _sse({"type": "agent_done", "agent": name, "file": file_path})

                    if name == "router" and hasattr(output, "next_workers"):
                        log.info("  → router decided  workers=%s", output.next_workers)

                    for msg in out_msgs:
                        # Only assistant replies are candidates — never echo the
                        # user's HumanMessage, which is re-emitted in node state.
                        if not isinstance(msg, AIMessage):
                            continue
                        c = getattr(msg, "content", "")
                        if isinstance(c, str) and c and not c.startswith("workspace/"):
                            ai_messages.append(c)

        except Exception as e:
            log.error("stream  graph error: %s\n%s", e, traceback.format_exc())
            yield _sse({"type": "error", "message": str(e)})
            return

        # Prefer the live-streamed summary text. Fall back to the collected
        # AIMessages only if streaming produced nothing (e.g. model without
        # streaming support).
        if streamed_text.strip():
            result = streamed_text
        else:
            result = ""
            for msg in reversed(ai_messages):
                if not re.match(r"^\[v\w+\]", msg):
                    result = msg
                    break

        # Agents are the workers that actually ran this turn; fall back to any
        # labels embedded in the result, else Maybach for a direct reply.
        agents = seen_agents or re.findall(r"\[(\w+)\]", result) or ["Maybach"]
        agents = list(dict.fromkeys(agents))
        clean = re.sub(r"^\[\w+\]\s*", "", result)

        # Persist conversation: prior history + this turn's human + final AI reply
        from langchain_core.messages import AIMessage as _AI
        _history = prior + [HumanMessage(content=req.task)]
        if clean:
            _history.append(_AI(content=clean))

        files = _deliverables(before_files)
        log.info("stream  done  agents=%s  files=%d  history_len=%d", agents, len(files), len(_history))
        yield _sse({"type": "done", "result": clean, "agents": agents, "files": files})

    return StreamingResponse(generate(), media_type="text/event-stream")


def _make_route(agent_module, label: str):
    """Factory that creates a FastAPI route handler for a single worker agent."""
    async def handler(req: TaskRequest) -> TaskResponse:
        log.info("agent/%s  task=%r", label, req.task[:80])
        try:
            result = agent_module.run(req.task)
            log.info("agent/%s  done", label)
            return TaskResponse(agent=label, result=result)
        except Exception as e:
            log.error("agent/%s  error: %s\n%s", label, e, traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))
    handler.__name__ = f"run_{label.lower()}"
    return handler


app.post("/agents/vda",  response_model=TaskResponse)(_make_route(vda_agent,  "vDA"))
app.post("/agents/vswe", response_model=TaskResponse)(_make_route(vswe_agent, "vSWE"))
app.post("/agents/vpm",  response_model=TaskResponse)(_make_route(vpm_agent,  "vPM"))
app.post("/agents/vds",  response_model=TaskResponse)(_make_route(vds_agent,  "vDS"))

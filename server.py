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
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

import agents.vda as vda_agent
import agents.vswe as vswe_agent
import agents.vpm as vpm_agent
import agents.vds as vds_agent
import orchestrator
from orchestrator import OrchestratorState

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

WORKER_NODES = {"vDA", "vPM", "vSWE", "vDS"}


class TaskRequest(BaseModel):
    task: str


class TaskResponse(BaseModel):
    agent: str
    result: str


class OrchestrateResponse(BaseModel):
    agents: list[str]
    result: str
    raw: str


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate_endpoint(req: TaskRequest) -> OrchestrateResponse:
    log.info("orchestrate  task=%r", req.task[:80])
    try:
        raw = orchestrator.run(req.task)
        all_labels = re.findall(r"\[(\w+)\]", raw)
        agents = list(dict.fromkeys(all_labels)) or ["Maybach"]
        match = re.match(r"^\[(\w+)\]\s*", raw)
        result = raw[match.end():] if match else raw
        log.info("orchestrate  done  agents=%s", agents)
        return OrchestrateResponse(agents=agents, result=result, raw=raw)
    except Exception as e:
        log.error("orchestrate  error: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/orchestrate/stream")
async def orchestrate_stream(req: TaskRequest):
    log.info("stream  task=%r", req.task[:80])

    async def generate():
        init_state = OrchestratorState(messages=[HumanMessage(content=req.task)])
        ai_messages: list[str] = []
        active_agent: str = ""

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
                    if name in WORKER_NODES:
                        msgs = output.get("messages", []) if isinstance(output, dict) else []
                        file_path = msgs[-1].content if msgs else ""
                        log.info("  → agent_done  agent=%s  file=%s", name, file_path)
                        yield _sse({"type": "agent_done", "agent": name, "file": file_path})

                    if isinstance(output, dict):
                        for msg in output.get("messages", []):
                            c = getattr(msg, "content", "")
                            if isinstance(c, str) and c and not c.startswith("workspace/"):
                                ai_messages.append(c)

        except Exception as e:
            log.error("stream  graph error: %s\n%s", e, traceback.format_exc())
            yield _sse({"type": "error", "message": str(e)})
            return

        result = ""
        for msg in reversed(ai_messages):
            if not re.match(r"^\[v\w+\]", msg):
                result = msg
                break

        all_labels = re.findall(r"\[(\w+)\]", result) if result else []
        agents = list(dict.fromkeys(all_labels)) or ["Maybach"]
        clean = re.sub(r"^\[\w+\]\s*", "", result)

        log.info("stream  done  agents=%s", agents)
        yield _sse({"type": "done", "result": clean, "agents": agents})

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

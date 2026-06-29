"""
FastAPI server with three surface areas:

  POST   /orchestrate          — full supervisor run, returns final result
  POST   /orchestrate/stream   — same run, streams SSE progress events
  POST   /agents/{name}        — single worker, bypasses the orchestrator
  DELETE /conversation         — clear the in-memory chat history
  GET    /files/*              — download/preview workspace deliverables

The stream endpoint emits an event for every routing decision, agent start,
tool call, summary token, and completion so the UI can show a live trace.
"""
import re
import json
import logging
import traceback
from config import load_config

# Must run before importing the orchestrator — sets OLLAMA_* from config.yaml.
load_config()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from tools.workspace_tools import _workspace

import agents.vda as vda_agent
import agents.vswe as vswe_agent
import agents.vpm as vpm_agent
import agents.vds as vds_agent
import orchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("maybach")

app = FastAPI(title="Maybach Agent Server", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the shared workspace so users can open/download deliverable files.
# Reachable from the UI via the /api/backend/files/* rewrite.
app.mount("/files", StaticFiles(directory=str(_workspace())), name="files")

# Per-agent summary files (vXX_<hex>.md) are internal, not user deliverables.
_SUMMARY_RE = re.compile(r"^v(?:da|pm|swe|ds)_[0-9a-f]+\.md$", re.IGNORECASE)


def _workspace_snapshot() -> set[str]:
    ws = _workspace()
    return {str(p.relative_to(ws)) for p in ws.rglob("*") if p.is_file()}


def _deliverables(before: set[str]) -> list[dict]:
    """Files created this turn that are user-facing deliverables.
    Excludes internal agent summaries and scratch checkpoints."""
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


# Single-session conversation memory — list of {"role", "content"} dicts.
_history: list[dict] = []


class TaskRequest(BaseModel):
    task: str


class TaskResponse(BaseModel):
    agent: str
    result: str


class OrchestrateResponse(BaseModel):
    agents: list[str]
    result: str
    files: list[dict] = []


def _sse(data: dict) -> str:
    # Server-Sent Events wire format: each message is `data: <json>\n\n`.
    # The browser's EventSource/stream reader splits on the blank line.
    return f"data: {json.dumps(data)}\n\n"


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
def orchestrate_endpoint(req: TaskRequest) -> OrchestrateResponse:
    global _history
    log.info("orchestrate  task=%r  history_len=%d", req.task[:80], len(_history))
    try:
        before = _workspace_snapshot()
        result, updated, agents = orchestrator.run(req.task, history=_history)
        _history = updated
        files = _deliverables(before)
        log.info("orchestrate  done  agents=%s  files=%d", agents, len(files))
        return OrchestrateResponse(agents=agents, result=result, files=files)
    except Exception as e:
        log.error("orchestrate  error: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/orchestrate/stream")
def orchestrate_stream(req: TaskRequest):
    # The live endpoint the UI uses. It forwards the orchestrator's events to
    # the browser as SSE, then sends a final `done` event with the result + the
    # list of files produced this turn.
    global _history
    log.info("stream  task=%r  history_len=%d", req.task[:80], len(_history))
    prior = list(_history)
    # Snapshot now; diff against it at the end to find this turn's new files.
    before_files = _workspace_snapshot()

    # Sync generator — Starlette iterates it in a threadpool, so the blocking
    # Ollama HTTP calls inside the orchestrator never stall the event loop.
    def generate():
        global _history
        result = ""
        agents = ["Maybach"]
        new_history = prior + [{"role": "user", "content": req.task}]

        try:
            # Pull events off the orchestrator one at a time and relay them.
            for ev in orchestrator.run_stream(req.task, prior):
                etype = ev["type"]
                if etype == "result":
                    # Internal sentinel (not sent to the UI) — carries the final
                    # text/agents/history. Folded into the `done` event below.
                    result = ev["result"]
                    agents = ev["agents"]
                    new_history = ev["history"]
                elif etype == "token":
                    yield _sse(ev)  # summary text, streamed to the UI live
                elif etype in (
                    "routing", "agent_start", "tool_call", "tool_done",
                    "agent_done", "summarizing", "direct", "error",
                ):
                    log.info("  → %s", _event_line(ev))
                    yield _sse(ev)
        except Exception as e:
            log.error("stream  error: %s\n%s", e, traceback.format_exc())
            yield _sse({"type": "error", "message": str(e)})
            return

        _history = new_history
        files = _deliverables(before_files)
        log.info("stream  done  agents=%s  files=%d  history_len=%d",
                 agents, len(files), len(_history))
        yield _sse({"type": "done", "result": result, "agents": agents, "files": files})

    return StreamingResponse(generate(), media_type="text/event-stream")


def _event_line(ev: dict) -> str:
    """Compact one-line log rendering of a stream event."""
    t = ev["type"]
    if t == "agent_start":
        return f"agent_start agent={ev['agent']}"
    if t == "agent_done":
        return f"agent_done agent={ev['agent']} file={ev.get('file', '')}"
    if t == "tool_call":
        return f"tool_call agent={ev.get('agent', '')} tool={ev.get('tool', '')}"
    if t == "tool_done":
        return f"tool_done agent={ev.get('agent', '')} tool={ev.get('tool', '')}"
    if t == "error":
        return f"error {ev.get('message', '')}"
    return t


def _make_route(agent_module, label: str):
    """Factory that creates a FastAPI route handler for a single worker agent.
    Used below to register POST /agents/vda, /agents/vswe, etc. — calling one
    worker directly, bypassing the router/summarizer."""
    def handler(req: TaskRequest) -> TaskResponse:
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

"""
FastAPI server with two surface areas:

  POST /orchestrate        — full supervisor graph (router + workers)
  POST /agents/{name}      — single worker, bypasses the orchestrator entirely

The /agents/* routes are useful for calling a specific worker from external
systems or for testing a worker in isolation without routing overhead.
"""
import re
from dotenv import load_dotenv

# Must run before agent imports — agents call get_llm() at module level
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import agents.vda as vda_agent
import agents.vswe as vswe_agent
import agents.vpm as vpm_agent
import agents.vds as vds_agent
import orchestrator

app = FastAPI(title="Maybach Agent Server", version="0.1.0")

# Allow the Next.js dev server to call this API without CORS errors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskRequest(BaseModel):
    task: str


class TaskResponse(BaseModel):
    agent: str
    result: str


class OrchestrateResponse(BaseModel):
    agents: list[str]  # all workers that ran, in order (deduped)
    result: str        # last AI message with the [LABEL] prefix stripped
    raw: str           # full last message including label, for debugging


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate(req: TaskRequest) -> OrchestrateResponse:
    try:
        raw = orchestrator.run(req.task)
        # Extract all [LABEL] tags from the response to show which workers ran.
        # dict.fromkeys preserves insertion order while deduping.
        all_labels = re.findall(r"\[(\w+)\]", raw)
        agents = list(dict.fromkeys(all_labels)) or ["unknown"]
        # Strip the leading [LABEL] prefix for the clean result shown in the UI
        match = re.match(r"^\[(\w+)\]\s*", raw)
        result = raw[match.end():] if match else raw
        return OrchestrateResponse(agents=agents, result=result, raw=raw)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _make_route(agent_module, label: str):
    """Factory that creates a FastAPI route handler for a single worker agent."""
    async def handler(req: TaskRequest) -> TaskResponse:
        try:
            result = agent_module.run(req.task)
            return TaskResponse(agent=label, result=result)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    # FastAPI uses __name__ to generate the OpenAPI operation ID
    handler.__name__ = f"run_{label.lower()}"
    return handler


app.post("/agents/vda",  response_model=TaskResponse)(_make_route(vda_agent,  "vDA"))
app.post("/agents/vswe", response_model=TaskResponse)(_make_route(vswe_agent, "vSWE"))
app.post("/agents/vpm",  response_model=TaskResponse)(_make_route(vpm_agent,  "vPM"))
app.post("/agents/vds",  response_model=TaskResponse)(_make_route(vds_agent,  "vDS"))

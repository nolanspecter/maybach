"""
FastAPI server exposing each worker agent and the full orchestrator.

Run: uvicorn server:app --reload --port 8000
"""
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import agents.vda as vda_agent
import agents.vswe as vswe_agent
import agents.vpm as vpm_agent
import agents.vds as vds_agent
import orchestrator

app = FastAPI(title="Maybach Agent Server", version="0.1.0")

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
    agents: list[str]   # all workers that ran (1 or more)
    result: str         # last AI message content (stripped of label)
    raw: str            # full last message including label


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate(req: TaskRequest) -> OrchestrateResponse:
    try:
        raw = orchestrator.run(req.task)
        # Worker responses are prefixed [LABEL]; direct responses have no prefix
        all_labels = re.findall(r"\[(\w+)\]", raw)
        agents = list(dict.fromkeys(all_labels)) or ["Maybach"]
        match = re.match(r"^\[(\w+)\]\s*", raw)
        result = raw[match.end():] if match else raw  # strip label if present
        return OrchestrateResponse(agents=agents, result=result, raw=raw)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _make_route(agent_module, label: str):
    async def handler(req: TaskRequest) -> TaskResponse:
        try:
            result = agent_module.run(req.task)
            return TaskResponse(agent=label, result=result)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    handler.__name__ = f"run_{label.lower()}"
    return handler


app.post("/agents/vda", response_model=TaskResponse)(_make_route(vda_agent, "vDA"))
app.post("/agents/vswe", response_model=TaskResponse)(_make_route(vswe_agent, "vSWE"))
app.post("/agents/vpm", response_model=TaskResponse)(_make_route(vpm_agent, "vPM"))
app.post("/agents/vds", response_model=TaskResponse)(_make_route(vds_agent, "vDS"))

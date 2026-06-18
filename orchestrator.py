"""
Orchestrator — supervisor that routes tasks to the right virtual employee.

Workers run in-process now. To go remote, replace the `_call_*` functions
with langgraph_sdk.RemoteGraph calls — the orchestrator logic stays the same.
"""
import os
from typing import Annotated, Literal
from dotenv import load_dotenv

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from pydantic import BaseModel

load_dotenv()

# ── Worker imports (swap these for RemoteGraph when extracting) ──────────────
import agents.vda as vda_agent
import agents.vswe as vswe_agent
import agents.vpm as vpm_agent
import agents.vds as vds_agent

MODEL = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250514-v1:0")

# ── State ────────────────────────────────────────────────────────────────────

class OrchestratorState(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages] = []
    next_worker: str = ""
    worker_result: str = ""


# ── Router ───────────────────────────────────────────────────────────────────

WORKERS = ["vDA", "vPM", "vSWE", "vDS", "FINISH"]

ROUTER_PROMPT = """You are a supervisor routing tasks to the right virtual employee.

Workers:
- vDA  — data analyst: SQL queries, data exploration, metrics, dashboards
- vPM  — product manager: PRDs, specs, roadmaps, requirements, prioritization
- vSWE — software engineer: writing code, debugging, building features, scripts
- vDS  — data scientist: ML models, statistical analysis, predictions, feature engineering
- FINISH — task is fully complete, no more routing needed

Given the conversation so far, choose exactly ONE worker to call next, or FINISH."""

class RouterDecision(BaseModel):
    next: Literal["vDA", "vPM", "vSWE", "vDS", "FINISH"]
    reasoning: str

_router_llm = ChatBedrockConverse(model=MODEL).with_structured_output(RouterDecision)


def router_node(state: OrchestratorState) -> OrchestratorState:
    messages = [("system", ROUTER_PROMPT)] + [
        ("human" if isinstance(m, HumanMessage) else "assistant", m.content)
        for m in state.messages
    ]
    decision: RouterDecision = _router_llm.invoke(messages)
    return OrchestratorState(
        messages=state.messages,
        next_worker=decision.next,
        worker_result=state.worker_result,
    )


def route_decision(state: OrchestratorState) -> str:
    return state.next_worker


# ── Worker nodes ─────────────────────────────────────────────────────────────

def _worker_node(agent_module, label: str):
    def node(state: OrchestratorState) -> OrchestratorState:
        last_human = next(
            (m.content for m in reversed(state.messages) if isinstance(m, HumanMessage)),
            "",
        )
        result = agent_module.run(last_human)
        reply = AIMessage(content=f"[{label}] {result}")
        return OrchestratorState(
            messages=state.messages + [reply],
            next_worker="",
            worker_result=result,
        )
    node.__name__ = label
    return node


vda_node = _worker_node(vda_agent, "vDA")
vswe_node = _worker_node(vswe_agent, "vSWE")
vpm_node = _worker_node(vpm_agent, "vPM")
vds_node = _worker_node(vds_agent, "vDS")


# ── Graph ─────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(OrchestratorState)

    g.add_node("router", router_node)
    g.add_node("vDA", vda_node)
    g.add_node("vPM", vpm_node)
    g.add_node("vSWE", vswe_node)
    g.add_node("vDS", vds_node)

    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        route_decision,
        {"vDA": "vDA", "vPM": "vPM", "vSWE": "vSWE", "vDS": "vDS", "FINISH": END},
    )
    # After each worker, go back to the router so it can decide to call another
    # worker or finish.
    for worker in ["vDA", "vPM", "vSWE", "vDS"]:
        g.add_edge(worker, "router")

    return g.compile()


graph = build_graph()


# ── Public API ────────────────────────────────────────────────────────────────

def run(task: str) -> str:
    """Run a task through the orchestrator and return the final result."""
    init_state = OrchestratorState(messages=[HumanMessage(content=task)])
    final_state = graph.invoke(init_state)
    # Return the last AI message
    for msg in reversed(final_state["messages"]):
        if isinstance(msg, AIMessage):
            return msg.content
    return "No result."

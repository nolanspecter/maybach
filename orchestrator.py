"""
Orchestrator — supervisor that routes tasks to one or more virtual employees,
running them in parallel when the router decides multiple workers are needed.

Fan-out uses LangGraph's Send API:
  router → [Send(vDA, state), Send(vSWE, state)] → (parallel) → aggregator → router | END

To go remote, replace the worker node bodies with RemoteGraph calls.
"""
from typing import Annotated, Literal
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import Send
from pydantic import BaseModel

load_dotenv()

from llm import get_llm
import agents.vda as vda_agent
import agents.vswe as vswe_agent
import agents.vpm as vpm_agent
import agents.vds as vds_agent

# ── State ─────────────────────────────────────────────────────────────────────

class OrchestratorState(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages] = []
    next_workers: list[str] = []


# ── Router ────────────────────────────────────────────────────────────────────

ROUTER_PROMPT = """You are a supervisor routing tasks to virtual employees.

Workers:
- vDA  — data analyst: SQL queries, data exploration, metrics, dashboards
- vPM  — product manager: PRDs, specs, roadmaps, requirements, prioritization
- vSWE — software engineer: writing code, debugging, building features, scripts
- vDS  — data scientist: ML models, statistical analysis, predictions, feature engineering
- FINISH — all work is done, return results to the user

Rules:
- Choose one OR multiple workers when tasks can be done in parallel (e.g. vDA + vDS together).
- Choose FINISH only when all necessary work is complete.
- FINISH must be the only entry in the list when chosen.
- Do not repeat a worker that already produced a result unless the task requires a follow-up."""

WorkerName = Literal["vDA", "vPM", "vSWE", "vDS", "FINISH"]

class RouterDecision(BaseModel):
    workers: list[WorkerName]
    reasoning: str

_router_llm = get_llm().with_structured_output(RouterDecision)


def router_node(state: OrchestratorState) -> OrchestratorState:
    messages = [("system", ROUTER_PROMPT)] + [
        ("human" if isinstance(m, HumanMessage) else "assistant", m.content)
        for m in state.messages
    ]
    decision: RouterDecision = _router_llm.invoke(messages)
    return OrchestratorState(messages=state.messages, next_workers=decision.workers)


def route_decision(state: OrchestratorState) -> list[Send] | str:
    workers = state.next_workers
    if not workers or workers == ["FINISH"]:
        return END
    return [Send(w, state) for w in workers]


# ── Worker nodes ──────────────────────────────────────────────────────────────

def _worker_node(agent_module, label: str):
    def node(state: OrchestratorState) -> OrchestratorState:
        last_human = next(
            (m.content for m in reversed(state.messages) if isinstance(m, HumanMessage)),
            "",
        )
        result = agent_module.run(last_human)
        reply = AIMessage(content=f"[{label}] {result}")
        return OrchestratorState(messages=[reply], next_workers=[])
    node.__name__ = label
    return node


vda_node  = _worker_node(vda_agent,  "vDA")
vswe_node = _worker_node(vswe_agent, "vSWE")
vpm_node  = _worker_node(vpm_agent,  "vPM")
vds_node  = _worker_node(vds_agent,  "vDS")


# ── Aggregator — join point after parallel workers ────────────────────────────

def aggregator_node(state: OrchestratorState) -> OrchestratorState:
    """Collects parallel worker results. Router decides what to do next."""
    return OrchestratorState(messages=state.messages, next_workers=[])


# ── Graph ─────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(OrchestratorState)

    g.add_node("router",     router_node)
    g.add_node("aggregator", aggregator_node)
    g.add_node("vDA",        vda_node)
    g.add_node("vPM",        vpm_node)
    g.add_node("vSWE",       vswe_node)
    g.add_node("vDS",        vds_node)

    g.add_edge(START, "router")

    # Fan-out: router → parallel workers (or END)
    g.add_conditional_edges("router", route_decision, ["vDA", "vPM", "vSWE", "vDS", END])

    # All workers join at aggregator, then loop back to router
    for worker in ["vDA", "vPM", "vSWE", "vDS"]:
        g.add_edge(worker, "aggregator")

    g.add_edge("aggregator", "router")

    return g.compile()


graph = build_graph()


# ── Public API ────────────────────────────────────────────────────────────────

def run(task: str) -> str:
    init_state = OrchestratorState(messages=[HumanMessage(content=task)])
    final_state = graph.invoke(init_state)
    for msg in reversed(final_state["messages"]):
        if isinstance(msg, AIMessage):
            return msg.content
    return "No result."

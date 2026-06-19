"""
Orchestrator — LangGraph supervisor that routes tasks to virtual employees.

Graph shape:
    START → router → [Send(vDA), Send(vSWE), ...] → aggregator → router → ... → END

The router can fan out to multiple workers in parallel via LangGraph's Send API.
After all parallel branches complete, the aggregator acts as a join point and
loops back to the router, which decides to call more workers or FINISH.

To go remote: replace the `agent_module.run()` calls in worker nodes with
RemoteGraph("name", url="...").invoke(...) — the orchestrator logic is unchanged.
"""
from typing import Annotated, Literal
from dotenv import load_dotenv

# Must run before llm/agent imports — get_llm() reads env vars at import time
load_dotenv()

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import Send
from pydantic import BaseModel

from llm import get_llm, HAIKU
import agents.vda as vda_agent
import agents.vswe as vswe_agent
import agents.vpm as vpm_agent
import agents.vds as vds_agent

# ── State ─────────────────────────────────────────────────────────────────────

class OrchestratorState(BaseModel):
    # add_messages reducer handles concurrent writes from parallel worker nodes
    messages: Annotated[list[BaseMessage], add_messages] = []
    # Workers chosen by the router for this turn (reset to [] after fan-out)
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

# Router uses Haiku — classification task, no heavy reasoning needed
_router_llm = get_llm(model=HAIKU).with_structured_output(RouterDecision)


def router_node(state: OrchestratorState) -> OrchestratorState:
    # Build a flat message list for the router; it needs to see the full
    # conversation to avoid re-dispatching workers that already responded
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
    # Return a Send per worker — LangGraph runs them concurrently
    return [Send(w, state) for w in workers]


# ── Worker nodes ──────────────────────────────────────────────────────────────

def _worker_node(agent_module, label: str):
    def node(state: OrchestratorState) -> OrchestratorState:
        # Always pass the original human task, not the accumulated conversation.
        # Workers are stateless — they receive one task and return one result.
        last_human = next(
            (m.content for m in reversed(state.messages) if isinstance(m, HumanMessage)),
            "",
        )
        result = agent_module.run(last_human)
        # Prefix with label so the server and UI can identify which worker responded
        reply = AIMessage(content=f"[{label}] {result}")
        # Return only the new message; add_messages reducer merges it into state
        return OrchestratorState(messages=[reply], next_workers=[])
    node.__name__ = label
    return node


vda_node  = _worker_node(vda_agent,  "vDA")
vswe_node = _worker_node(vswe_agent, "vSWE")
vpm_node  = _worker_node(vpm_agent,  "vPM")
vds_node  = _worker_node(vds_agent,  "vDS")


# ── Aggregator ────────────────────────────────────────────────────────────────

def aggregator_node(state: OrchestratorState) -> OrchestratorState:
    # Join point after parallel workers complete. State is already merged by
    # add_messages at this point — just reset next_workers and loop to router.
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

    # Conditional fan-out: router returns list[Send] for parallel workers, or END
    g.add_conditional_edges("router", route_decision, ["vDA", "vPM", "vSWE", "vDS", END])

    # All workers converge at aggregator before the next router decision
    for worker in ["vDA", "vPM", "vSWE", "vDS"]:
        g.add_edge(worker, "aggregator")

    g.add_edge("aggregator", "router")

    return g.compile()


graph = build_graph()


# ── Public API ────────────────────────────────────────────────────────────────

def run(task: str) -> str:
    """Run a task through the full supervisor graph and return the final AI message."""
    init_state = OrchestratorState(messages=[HumanMessage(content=task)])
    final_state = graph.invoke(init_state)
    for msg in reversed(final_state["messages"]):
        if isinstance(msg, AIMessage):
            return msg.content
    return "No result."

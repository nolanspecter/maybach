"""
Orchestrator — LangGraph supervisor that routes tasks to virtual employees.

Graph shape:
    START → router → [Send(vDA), Send(vSWE), ...] → aggregator → router → ... → END
                   → direct → router → END
                   → END  (FINISH)

The router can:
  - Fan out to one or more workers in parallel (Send API)
  - Respond directly for conversational messages (DIRECT)
  - Terminate (FINISH)

To go remote: replace agent_module.run() calls with RemoteGraph.invoke().
"""
from typing import Annotated, Literal
from dotenv import load_dotenv

# Must run before llm/agent imports — get_llm() reads env vars at module level
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
    next_workers: list[str] = []


# ── Router ────────────────────────────────────────────────────────────────────

ROUTER_PROMPT = """You are Maybach, an AI assistant with a team of virtual employees.

Available workers:
- vDA  — data analyst: SQL queries, data exploration, metrics, dashboards
- vPM  — product manager: PRDs, specs, roadmaps, requirements, prioritization
- vSWE — software engineer: writing code, debugging, building features, scripts
- vDS  — data scientist: ML models, statistical analysis, predictions, feature engineering
- DIRECT — respond yourself ONLY for: pure greetings, small talk, or meta questions
           about Maybach's capabilities with zero actionable work content
- FINISH — all work is done, return results to the user

Decision process (follow every time):
1. Break the message into sub-tasks. What is being asked, explicitly or implicitly?
2. For each sub-task, ask: does this need specialist knowledge or tools?
   - Data queries, numbers, tables    → vDA
   - Specs, plans, requirements       → vPM
   - Code, scripts, debugging         → vSWE
   - Models, statistics, ML           → vDS
   - Nothing needs a worker           → DIRECT
3. Dispatch independent sub-tasks to workers in parallel.
4. Err toward calling a worker — specialists add more value than a direct reply.

Rules:
- NEVER use DIRECT if any part of the message could benefit from a specialist worker.
- FINISH must be the only entry in the list when chosen.
- Do not repeat a worker that already produced a result unless follow-up is needed."""

WorkerName = Literal["vDA", "vPM", "vSWE", "vDS", "DIRECT", "FINISH"]

class RouterDecision(BaseModel):
    workers: list[WorkerName]
    reasoning: str

# Router uses Haiku — classification only, no heavy reasoning needed
_router_llm = get_llm(model=HAIKU).with_structured_output(RouterDecision)


def router_node(state: OrchestratorState) -> OrchestratorState:
    # Pass full conversation so router avoids re-calling workers that already responded
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
    if workers == ["DIRECT"]:
        return "direct"
    # Return one Send per worker — LangGraph runs them concurrently
    return [Send(w, state) for w in workers]


# ── Direct response node ──────────────────────────────────────────────────────

DIRECT_PROMPT = """You are Maybach, an AI assistant backed by a team of virtual employees:
- vDA (Data Analyst) — SQL queries, data exploration, metrics
- vPM (Product Manager) — PRDs, specs, roadmaps, backlogs
- vSWE (Software Engineer) — code, debugging, scripts
- vDS (Data Scientist) — ML models, statistics, predictions

For conversational messages, respond naturally and helpfully.
When describing your capabilities, be concrete about what each worker can do."""

# Direct node uses the full worker model — quality matters for user-facing replies
_direct_llm = get_llm()


def direct_node(state: OrchestratorState) -> OrchestratorState:
    messages = [("system", DIRECT_PROMPT)] + [
        ("human" if isinstance(m, HumanMessage) else "assistant", m.content)
        for m in state.messages
    ]
    response = _direct_llm.invoke(messages)
    reply = AIMessage(content=response.content)
    return OrchestratorState(messages=[reply], next_workers=[])


# ── Worker nodes ──────────────────────────────────────────────────────────────

def _worker_node(agent_module, label: str):
    def node(state: OrchestratorState) -> OrchestratorState:
        # Workers are stateless — always receive the original human task
        last_human = next(
            (m.content for m in reversed(state.messages) if isinstance(m, HumanMessage)),
            "",
        )
        result = agent_module.run(last_human)
        # Prefix with label so server/UI can identify which worker responded
        reply = AIMessage(content=f"[{label}] {result}")
        # Return only new message; add_messages reducer merges it into shared state
        return OrchestratorState(messages=[reply], next_workers=[])
    node.__name__ = label
    return node


vda_node  = _worker_node(vda_agent,  "vDA")
vswe_node = _worker_node(vswe_agent, "vSWE")
vpm_node  = _worker_node(vpm_agent,  "vPM")
vds_node  = _worker_node(vds_agent,  "vDS")


# ── Aggregator — join point after parallel workers ────────────────────────────

def aggregator_node(state: OrchestratorState) -> OrchestratorState:
    # State already merged by add_messages; just reset next_workers and loop to router
    return OrchestratorState(messages=state.messages, next_workers=[])


# ── Graph ─────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(OrchestratorState)

    g.add_node("router",     router_node)
    g.add_node("direct",     direct_node)
    g.add_node("aggregator", aggregator_node)
    g.add_node("vDA",        vda_node)
    g.add_node("vPM",        vpm_node)
    g.add_node("vSWE",       vswe_node)
    g.add_node("vDS",        vds_node)

    g.add_edge(START, "router")

    # Fan-out: router → parallel workers, direct response, or END
    g.add_conditional_edges(
        "router", route_decision,
        ["vDA", "vPM", "vSWE", "vDS", "direct", END]
    )

    # All workers converge at aggregator before the next router decision
    for worker in ["vDA", "vPM", "vSWE", "vDS"]:
        g.add_edge(worker, "aggregator")

    g.add_edge("aggregator", "router")

    # After a direct reply, loop to router so it can chain workers if needed
    g.add_edge("direct", "router")

    return g.compile()


graph = build_graph()


# ── Public API ────────────────────────────────────────────────────────────────

def run(task: str) -> str:
    """Run a task or message through the supervisor graph and return the final response."""
    init_state = OrchestratorState(messages=[HumanMessage(content=task)])
    final_state = graph.invoke(init_state)
    for msg in reversed(final_state["messages"]):
        if isinstance(msg, AIMessage):
            return msg.content
    return "No result."

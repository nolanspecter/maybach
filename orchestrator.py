"""
Orchestrator — LangGraph supervisor that routes tasks to virtual employees.

Graph shape:
    START → router → [Send(vDA), Send(vSWE), ...] → aggregator → router → FINISH → summarizer → END
                   → direct → END

Workers write output to workspace/ and return the file path.
Summarizer reads those files and synthesises a final response for the user.
"""
import re
from pathlib import Path
from typing import Annotated, Literal
from config import load_config

# Must run before llm/agent imports — get_llm() reads env vars at module level
load_config()

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

def _last_value(a: list[str], b: list[str]) -> list[str]:
    # Workers all write [] to next_workers — last writer wins is fine here
    return b


class OrchestratorState(BaseModel):
    # add_messages reducer handles concurrent writes from parallel worker nodes
    messages: Annotated[list[BaseMessage], add_messages] = []
    # _last_value reducer needed when parallel workers write next_workers simultaneously
    next_workers: Annotated[list[str], _last_value] = []


# ── Router ────────────────────────────────────────────────────────────────────

ROUTER_PROMPT = """You are Maybach, an AI assistant with a team of virtual employees.

Available workers:
- vDA  — data analyst: SQL queries, data exploration, metrics, dashboards
- vPM  — product manager: PRDs, specs, roadmaps, requirements, prioritization
- vSWE — software engineer: writing code, debugging, building features, scripts
- vDS  — data scientist: ML models, statistical analysis, predictions, feature engineering
- DIRECT — respond yourself for greetings, small talk, general questions, capability
           questions, or anything that does NOT require data/code/specs/models
- FINISH — a worker has already responded and the task is complete

Decision process (follow every time):
1. Check if workers have already responded (look for [vDA], [vPM], [vSWE], [vDS] in history).
   - If yes → choose FINISH unless the user explicitly asked for follow-up work.
2. If no workers have responded yet, classify the message:
   - Greeting, small talk, "what can you do?" → DIRECT
   - Needs data/SQL/numbers → vDA
   - Needs specs/PRD/roadmap → vPM
   - Needs code/script/debug → vSWE
   - Needs ML/stats/model → vDS
   - Multiple independent needs → multiple workers in parallel

Rules:
- FINISH immediately after workers respond — do not loop back to workers unless asked.
- FINISH must be the only entry in the list when chosen.
- Do not repeat a worker already in history unless the user asked for a follow-up."""

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
        return "summarizer"
    if workers == ["DIRECT"]:
        return "direct"
    return [Send(w, state) for w in workers]


# ── Direct response node ──────────────────────────────────────────────────────

DIRECT_PROMPT = """You are Maybach, an AI assistant backed by a team of virtual employees:
- vDA (Data Analyst) — SQL queries, data exploration, metrics
- vPM (Product Manager) — PRDs, specs, roadmaps, backlogs
- vSWE (Software Engineer) — code, debugging, scripts
- vDS (Data Scientist) — ML models, statistics, predictions

For conversational messages, respond naturally and helpfully.
When describing your capabilities, be concrete about what each worker can do."""

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
        # agent.run() writes output to workspace/ and returns the file path
        file_path = agent_module.run(last_human)
        reply = AIMessage(content=f"[{label}] {file_path}")
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


# ── Summarizer — reads workspace files and responds to the user ───────────────

SUMMARIZER_PROMPT = """You are Maybach. Virtual employees have completed their work and
saved results to files. Read their outputs and synthesise a clear, concise response
for the user. Combine insights where relevant. Don't just repeat file contents — interpret
and present the key points."""

_summarizer_llm = get_llm()


def summarizer_node(state: OrchestratorState) -> OrchestratorState:
    # Extract workspace paths from worker messages like "[vDA] workspace/vda_abc123.md"
    worker_outputs = []
    for msg in state.messages:
        if not isinstance(msg, AIMessage):
            continue
        match = re.match(r"^\[(\w+)\]\s*(workspace/\S+)", msg.content)
        if not match:
            continue
        label, path_str = match.group(1), match.group(2)
        path = Path(path_str)
        if path.exists():
            content = path.read_text(encoding="utf-8")
            worker_outputs.append(f"## [{label}] output\n{content}")

    user_question = next(
        (m.content for m in state.messages if isinstance(m, HumanMessage)), ""
    )

    if not worker_outputs:
        # No worker files found — shouldn't happen, but fail gracefully
        reply = AIMessage(content="Workers completed but no output files were found.")
        return OrchestratorState(messages=[reply], next_workers=[])

    summary_input = (
        f"User asked: {user_question}\n\n"
        + "\n\n".join(worker_outputs)
    )
    messages = [("system", SUMMARIZER_PROMPT), ("human", summary_input)]
    response = _summarizer_llm.invoke(messages)
    reply = AIMessage(content=response.content)
    return OrchestratorState(messages=[reply], next_workers=[])


# ── Graph ─────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(OrchestratorState)

    g.add_node("router",     router_node)
    g.add_node("direct",     direct_node)
    g.add_node("aggregator", aggregator_node)
    g.add_node("summarizer", summarizer_node)
    g.add_node("vDA",        vda_node)
    g.add_node("vPM",        vpm_node)
    g.add_node("vSWE",       vswe_node)
    g.add_node("vDS",        vds_node)

    g.add_edge(START, "router")

    # Fan-out: router → parallel workers, direct response, or summarizer
    g.add_conditional_edges(
        "router", route_decision,
        ["vDA", "vPM", "vSWE", "vDS", "direct", "summarizer"]
    )

    # All workers converge at aggregator, then back to router for FINISH decision
    for worker in ["vDA", "vPM", "vSWE", "vDS"]:
        g.add_edge(worker, "aggregator")

    g.add_edge("aggregator", "router")

    # Summarizer and direct are both terminal
    g.add_edge("summarizer", END)
    g.add_edge("direct", END)

    return g.compile()


graph = build_graph()


# ── Public API ────────────────────────────────────────────────────────────────

def run(task: str) -> str:
    """Run a task through the supervisor graph and return the final synthesised response."""
    init_state = OrchestratorState(messages=[HumanMessage(content=task)])
    final_state = graph.invoke(init_state, config={"recursion_limit": 50})
    for msg in reversed(final_state["messages"]):
        if isinstance(msg, AIMessage):
            return msg.content
    return "No result."

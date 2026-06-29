"""
Maybach orchestrator — a hand-rolled supervisor (no LangGraph).

One turn, one pass — structurally loop-free:

    router  ─┬─ DIRECT ──────────────► stream reply
             └─ one or more workers ──► summarizer ──► stream reply

The router is an LLM JSON classifier. Workers run sequentially; each writes its
output to workspace/ and returns the file path. The summarizer reads those files
and streams a synthesised answer to the user.

History is a list of plain {"role", "content"} dicts. Only the user's message
and the final assistant reply are persisted per turn — the per-worker file
pointers stay internal so the router never re-dispatches a finished worker.

Public API:
    run_stream(task, history) -> Iterator[event dict]   # for SSE
    run(task, history)        -> (reply, history, agents)
"""
from __future__ import annotations

import json
import queue
import re
import threading
from pathlib import Path
from typing import Iterator

from config import load_config

# Must run before any client is constructed — sets OLLAMA_* from config.yaml.
load_config()

from core.llm import OllamaClient, router_model
from core.output import deliverable_snapshot
import agents.vda as vda_agent
import agents.vpm as vpm_agent
import agents.vswe as vswe_agent
import agents.vds as vds_agent

WORKERS = {
    "vDA": vda_agent,
    "vPM": vpm_agent,
    "vSWE": vswe_agent,
    "vDS": vds_agent,
}
_VALID = set(WORKERS) | {"DIRECT", "FINISH"}

# ── Prompts ───────────────────────────────────────────────────────────────────

ROUTER_PROMPT = """You are Maybach, an AI assistant with a team of virtual employees.

Available workers:
- vDA  — data analyst: SQL queries, data exploration, metrics, dashboards
- vPM  — product manager: PRDs, specs, roadmaps, requirements, prioritization
- vSWE — software engineer: writing code, debugging, building features, scripts
- vDS  — data scientist: ML models, statistical analysis, predictions, feature engineering
- DIRECT — respond yourself for greetings, small talk, general questions, or
           capability questions that do NOT require data/code/specs/models

Classify the user's LATEST message:
- Greeting, small talk, "what can you do?"  → ["DIRECT"]
- Needs data / SQL / numbers                 → ["vDA"]
- Needs specs / PRD / roadmap                → ["vPM"]
- Needs code / script / debug / build a file → ["vSWE"]
- Needs ML / stats / model / prediction      → ["vDS"]
- Several independent needs                   → list every worker required

Respond with ONLY a JSON object, no prose:
{"workers": ["vSWE"], "reasoning": "short why"}"""

DIRECT_PROMPT = """You are Maybach, an AI assistant backed by a team of virtual employees:
- vDA (Data Analyst) — SQL queries, data exploration, metrics
- vPM (Product Manager) — PRDs, specs, roadmaps, backlogs
- vSWE (Software Engineer) — code, debugging, scripts
- vDS (Data Scientist) — ML models, statistics, predictions

For conversational messages, respond naturally and helpfully.
When describing your capabilities, be concrete about what each worker can do."""

SUMMARIZER_PROMPT = """You are Maybach. Virtual employees have completed their work.
You are given the list of files they saved this turn and their notes. Write a clear,
concise reply for the user.

Honesty rules — follow exactly:
- Only say a file, app, or page was created if it appears in the "Files saved" list.
- If the user asked for a file/app/page and that list is "(none)", tell them it was
  NOT saved this time and include the content inline so they still have it. Never
  claim a deliverable exists when it does not.
- When files exist, refer to them by name so the user knows what to open or download.

Interpret and present the key points — don't just dump file contents."""

# ── Clients ───────────────────────────────────────────────────────────────────

_client = OllamaClient()                      # direct + summarizer (main model)
_router = OllamaClient(model=router_model())  # classification only


# ── Router ────────────────────────────────────────────────────────────────────

def _transcript(history: list[dict]) -> str:
    return "\n".join(f'{m["role"]}: {m["content"]}' for m in history)


def _route(turn: list[dict]) -> list[str]:
    """Ask the router which workers (if any) should handle this turn."""
    messages = [
        {"role": "system", "content": ROUTER_PROMPT},
        {"role": "user", "content": _transcript(turn)},
    ]
    msg = _router.chat(messages, fmt="json", temperature=0)
    raw = (msg.get("content") or "").strip()
    try:
        workers = json.loads(raw).get("workers", [])
    except (json.JSONDecodeError, AttributeError, TypeError):
        workers = []
    workers = [w for w in workers if w in _VALID]
    # Anything unclassifiable → answer directly rather than stall.
    return workers or ["DIRECT"]


# ── Streaming entry point ─────────────────────────────────────────────────────

def run_stream(task: str, history: list[dict] | None = None) -> Iterator[dict]:
    """Drive one turn, yielding UI events. The final event is
    {"type": "result", "result", "agents", "history"}."""
    prior = list(history or [])
    turn = prior + [{"role": "user", "content": task}]

    yield {"type": "routing"}
    decision = _route(turn)
    workers = [w for w in decision if w in WORKERS]

    if not workers:
        # ── Direct path ──────────────────────────────────────────────────────
        yield {"type": "direct"}
        reply = yield from _stream_reply(
            [{"role": "system", "content": DIRECT_PROMPT}] + turn
        )
        yield _result(reply, ["Maybach"], turn)
        return

    # ── Worker path ──────────────────────────────────────────────────────────
    before_files = deliverable_snapshot()  # to report what this turn actually saved
    ran: list[str] = []
    outputs: list[str] = []
    for name in workers:
        yield {"type": "agent_start", "agent": name}
        try:
            file_path = yield from _run_worker(name, task)
        except Exception as e:  # noqa: BLE001 — report and keep going
            yield {"type": "error", "message": f"{name} failed: {e}"}
            continue
        ran.append(name)
        yield {"type": "agent_done", "agent": name, "file": file_path}

        body = _read_output(file_path)
        if body is not None:
            outputs.append(f"## [{name}] output\n{body}")

    # ── Summarize ────────────────────────────────────────────────────────────
    yield {"type": "summarizing"}
    produced = sorted(deliverable_snapshot() - before_files)
    reply = yield from _stream_reply([
        {"role": "system", "content": SUMMARIZER_PROMPT},
        {"role": "user", "content": _summary_input(task, outputs, produced)},
    ])
    yield _result(reply, ran or ["Maybach"], turn)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _summary_input(task: str, outputs: list[str], produced: list[str]) -> str:
    """Grounded summarizer input: the real file list + the workers' notes, so
    the reply can only honestly reference files that were actually saved."""
    files = "\n".join(f"- {f}" for f in produced) if produced else "- (none)"
    notes = "\n\n".join(outputs) if outputs else "(workers produced no readable notes)"
    return (
        f"User asked: {task}\n\n"
        f"Files saved to the workspace this turn (downloadable by the user):\n{files}\n\n"
        f"Worker notes:\n{notes}"
    )


def _stream_reply(messages: list[dict]) -> Iterator[dict]:
    """Stream a model reply token-by-token, yielding {"type":"token"} events.
    Returns the full text (via generator return)."""
    parts: list[str] = []
    for tok in _client.stream(messages):
        parts.append(tok)
        yield {"type": "token", "text": tok}
    return "".join(parts)


def _run_worker(name: str, task: str) -> Iterator[dict]:
    """Run a worker in a thread so its tool events stream live while the
    blocking agent loop executes. Returns the worker's output file path."""
    q: queue.Queue = queue.Queue()
    box: dict = {}

    def work():
        try:
            box["file"] = WORKERS[name].run(task, on_event=q.put)
        except Exception as e:  # noqa: BLE001 — surfaced to caller below
            box["error"] = e
        finally:
            q.put(None)  # sentinel: worker finished

    t = threading.Thread(target=work, daemon=True)
    t.start()
    while True:
        ev = q.get()
        if ev is None:
            break
        yield ev
    t.join()

    if "error" in box:
        raise box["error"]
    return box.get("file", "")


def _read_output(file_path: str) -> str | None:
    """Read a worker's workspace file, or None if missing."""
    if not file_path:
        return None
    p = Path(file_path)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return None


def _result(reply: str, agents: list[str], turn: list[dict]) -> dict:
    new_history = turn + [{"role": "assistant", "content": reply}]
    return {"type": "result", "result": reply, "agents": agents, "history": new_history}


# ── Non-streaming entry point ─────────────────────────────────────────────────

def run(task: str, history: list[dict] | None = None) -> tuple[str, list[dict], list[str]]:
    """Run one turn without streaming.
    Returns (reply_text, updated_history, agents_that_ran)."""
    reply, new_history, agents = "", list(history or []), ["Maybach"]
    for ev in run_stream(task, history):
        if ev["type"] == "result":
            reply = ev["result"]
            new_history = ev["history"]
            agents = ev["agents"]
    return reply, new_history, agents

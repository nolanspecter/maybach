"""Smoke test — exercises the whole harness with a faked Ollama client.

No live model, no network. Monkeypatches OllamaClient.chat/stream at the class
level so every agent + the orchestrator run against scripted responses. Run:

    python3 tests/test_smoke.py
"""
import json
import os
import sys
import tempfile

# Isolate workspace writes to a throwaway dir before anything imports it.
os.environ["WORKSPACE_DIR"] = tempfile.mkdtemp(prefix="maybach_test_")

# Make the project root importable when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.llm as llm_mod  # noqa: E402

# ── Fake Ollama ───────────────────────────────────────────────────────────────
_ROUTER_DECISION = {"workers": ["DIRECT"]}   # mutated per test
_worker_calls: dict[int, int] = {}           # per-client call counter


def fake_chat(self, messages, tools=None, fmt=None, model=None, temperature=None):
    if fmt == "json":                         # router classification
        return {"role": "assistant", "content": json.dumps(_ROUTER_DECISION)}
    if tools:                                 # worker ReAct loop
        n = _worker_calls.get(id(self), 0) + 1
        _worker_calls[id(self)] = n
        if n == 1:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "function": {
                        "name": "write_file",
                        "arguments": {"filename": "index.html",
                                      "content": "<h1>hello</h1>"},
                    }
                }],
            }
        return {"role": "assistant", "content": "Built index.html. Done."}
    return {"role": "assistant", "content": "final"}


def fake_stream(self, messages, model=None, temperature=None):
    for tok in ["Here ", "is ", "the ", "summary."]:
        yield tok


# A model that returns its tool call as JSON-in-text (no native tool_calls),
# the way llama3.2 sometimes does. Used by test_text_fallback.
_text_calls: dict[int, int] = {}


def fake_chat_text_tool(self, messages, tools=None, fmt=None, model=None, temperature=None):
    n = _text_calls.get(id(self), 0) + 1
    _text_calls[id(self)] = n
    if n == 1:
        return {
            "role": "assistant",
            "content": '```json\n{"name": "write_file", "parameters": '
                       '{"filename": "note.txt", "content": "hi"}}\n```',
        }
    return {"role": "assistant", "content": "Saved note.txt."}


llm_mod.OllamaClient.chat = fake_chat
llm_mod.OllamaClient.stream = fake_stream

# Import AFTER patching so module-level clients use the fakes at call time.
from core.tools import tool            # noqa: E402
from core.agent import Agent           # noqa: E402
from tools.workspace_tools import write_file, _workspace  # noqa: E402
import orchestrator                    # noqa: E402

PASS, FAIL = "✓", "✗"
_failures = 0


def check(name, cond):
    global _failures
    print(f"  {PASS if cond else FAIL} {name}")
    if not cond:
        _failures += 1


# ── Test A: tool framework ────────────────────────────────────────────────────
def test_tools():
    print("tool framework")

    @tool
    def add(a: int, b: int = 2) -> str:
        """Add two numbers."""
        return str(a + b)

    spec = add.spec
    check("spec has function name", spec["function"]["name"] == "add")
    check("description from docstring", spec["function"]["description"] == "Add two numbers.")
    props = spec["function"]["parameters"]["properties"]
    check("int → integer", props["a"]["type"] == "integer")
    check("required excludes defaulted arg", spec["function"]["parameters"]["required"] == ["a"])
    check("invoke runs the function", add.invoke({"a": 3}) == "5")
    check("bad args return error text", add.invoke({"x": 1}).startswith("Error"))


# ── Test B: agent ReAct loop ──────────────────────────────────────────────────
def test_agent_loop():
    print("agent ReAct loop")
    events = []
    a = Agent("vSWE", "system", [write_file])
    out = a.run("build a page", on_event=events.append)
    types = [e["type"] for e in events]
    check("emitted tool_call", "tool_call" in types)
    check("emitted tool_done", "tool_done" in types)
    check("tool_call names the tool", any(e.get("tool") == "write_file" for e in events))
    check("final answer returned", "Done" in out)
    check("file actually written", (_workspace() / "index.html").exists())


# ── Test C: orchestrator DIRECT path ──────────────────────────────────────────
def test_direct():
    print("orchestrator — direct path")
    global _ROUTER_DECISION
    _ROUTER_DECISION = {"workers": ["DIRECT"]}
    evs = list(orchestrator.run_stream("hello there"))
    types = [e["type"] for e in evs]
    check("routing first", types[0] == "routing")
    check("direct emitted", "direct" in types)
    check("tokens streamed", "token" in types)
    check("no worker started", "agent_start" not in types)
    result = [e for e in evs if e["type"] == "result"][0]
    check("result text assembled", result["result"] == "Here is the summary.")
    check("agents = Maybach", result["agents"] == ["Maybach"])
    check("history has user+assistant", len(result["history"]) == 2)


# ── Test D: orchestrator worker path ──────────────────────────────────────────
def test_worker_path():
    print("orchestrator — worker path")
    global _ROUTER_DECISION
    _ROUTER_DECISION = {"workers": ["vSWE"]}
    evs = list(orchestrator.run_stream("build me an HTML page"))
    types = [e["type"] for e in evs]
    check("agent_start vSWE", any(e["type"] == "agent_start" and e["agent"] == "vSWE" for e in evs))
    check("tool events streamed from worker", "tool_call" in types)
    check("agent_done with file", any(e["type"] == "agent_done" and e.get("file") for e in evs))
    check("summarizing emitted", "summarizing" in types)
    check("summary tokens streamed", "token" in types)
    result = [e for e in evs if e["type"] == "result"][0]
    check("agents = [vSWE]", result["agents"] == ["vSWE"])
    check("deliverable index.html exists", (_workspace() / "index.html").exists())


# ── Test E: non-streaming run() ───────────────────────────────────────────────
def test_run_tuple():
    print("orchestrator.run() non-streaming")
    global _ROUTER_DECISION
    _ROUTER_DECISION = {"workers": ["DIRECT"]}
    reply, history, agents = orchestrator.run("hi")
    check("reply is text", reply == "Here is the summary.")
    check("agents is list", agents == ["Maybach"])
    check("history threaded", history[-1]["role"] == "assistant")
    # second turn carries prior history
    reply2, history2, _ = orchestrator.run("again", history=history)
    check("history grows across turns", len(history2) == 4)


def test_output_guarantee_and_salvage():
    print("output — guaranteed file + code salvage")
    import core.output as out

    # Empty model output still yields a non-empty job file.
    path = out.write_job_output("vSWE", "")
    p = _workspace() / path.split("/", 1)[1]
    check("job file always written", p.exists())
    check("job file never empty", p.read_text().strip() != "")

    # Code block + a named filename → salvaged under that name.
    before = out.deliverable_snapshot()
    content = "Here is the script.\n```python\nprint('hi')\n```\nI saved it as hello.py."
    written = out.salvage_deliverables("vSWE", content, before)
    check("named code block salvaged as hello.py", "hello.py" in written)
    check("salvaged file has the code", "print('hi')" in (_workspace() / "hello.py").read_text())

    # Code block with no filename → generic name from label.
    before = out.deliverable_snapshot()
    written = out.salvage_deliverables("vDS", "```python\nx = 1\n```", before)
    check("unnamed block gets generic name", written == ["vds_output1.py"])

    # If a deliverable already exists from this run, salvage is skipped.
    before = out.deliverable_snapshot()
    (_workspace() / "explicit.txt").write_text("saved by write_file", encoding="utf-8")
    written = out.salvage_deliverables("vSWE", "```python\ny = 2\n```", before)
    check("salvage skipped when deliverable already written", written == [])

    # Prose/console blocks are not salvaged.
    before = out.deliverable_snapshot()
    written = out.salvage_deliverables("vSWE", "Output:\n```\n4\n```", before)
    check("plain (non-code) block not salvaged", written == [])


def test_text_fallback():
    print("agent — JSON-in-text tool-call fallback")
    llm_mod.OllamaClient.chat = fake_chat_text_tool
    try:
        events = []
        a = Agent("vSWE", "system", [write_file])
        out = a.run("save a note", on_event=events.append)
        check("tool recovered from text", any(e["type"] == "tool_call" for e in events))
        check("recovered tool ran write_file", (_workspace() / "note.txt").exists())
        check("final answer after recovery", "Saved" in out)
    finally:
        llm_mod.OllamaClient.chat = fake_chat  # restore for any later tests


if __name__ == "__main__":
    for t in (test_tools, test_agent_loop, test_output_guarantee_and_salvage,
              test_text_fallback, test_direct, test_worker_path, test_run_tuple):
        t()
    print()
    if _failures:
        print(f"{FAIL} {_failures} check(s) failed")
        sys.exit(1)
    print(f"{PASS} all checks passed")

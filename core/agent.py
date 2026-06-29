"""A ReAct agent loop over the Ollama client — no LangChain.

The agent calls the model with its tool specs. While the model responds with
tool calls, it executes them, appends the results to the running message list,
and loops. When the model returns a plain text answer (no tool calls) — or the
iteration cap is hit — the agent returns that text.

Tool activity is reported through an optional `on_event` callback so the
orchestrator can stream `tool_call` / `tool_done` events to the UI.
"""
from __future__ import annotations

import json
from typing import Callable

from core.llm import OllamaClient
from core.tools import Tool

EventCb = Callable[[dict], None]


def _preview(args: dict) -> str:
    """Short, safe one-line preview of tool arguments for the live log."""
    try:
        s = json.dumps(args, ensure_ascii=False)
    except (TypeError, ValueError):
        s = str(args)
    return s[:120]


def _find_json_objects(text: str) -> list[str]:
    """Return every balanced top-level {...} substring in text."""
    objs: list[str] = []
    depth = 0
    start = None
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                objs.append(text[start:i + 1])
                start = None
    return objs


def _parse_text_tool_calls(content: str, known: set[str]) -> list[dict]:
    """Recover tool calls a model emitted as JSON in its text instead of as
    native tool_calls. Only matches objects naming a known tool, so a final
    answer that merely contains JSON is never mistaken for a call.

    Handles the common shapes:
        {"name": "run_python", "parameters": {...}}
        {"name": "run_python", "arguments": {...}}
        {"function": {"name": "run_python", "arguments": {...}}}
    """
    calls: list[dict] = []
    for raw in _find_json_objects(content):
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue

        fn = obj.get("function")
        if isinstance(fn, dict):
            name = fn.get("name")
            args = fn.get("arguments", fn.get("parameters"))
        else:
            name = obj.get("name") or obj.get("tool")
            args = obj.get("arguments")
            if args is None:
                args = obj.get("parameters")
            if args is None:
                args = obj.get("args")

        if isinstance(name, str) and name in known:
            calls.append({"function": {"name": name, "arguments": args or {}}})
    return calls


class Agent:
    def __init__(
        self,
        name: str,
        system_prompt: str,
        tools: list[Tool],
        model: str | None = None,
        max_iters: int = 8,
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = {t.name: t for t in tools}
        self.specs = [t.spec for t in tools]
        self.client = OllamaClient(model=model)
        self.max_iters = max_iters

    def run(self, task: str, on_event: EventCb | None = None) -> str:
        # `messages` is the running conversation we resend to the model every
        # iteration. Four roles are used:
        #   system    — the agent's instructions (sent once, first)
        #   user      — the task
        #   assistant — what the model said (may carry tool_calls)
        #   tool      — the result of running a tool, fed back to the model
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task},
        ]
        last_text = ""

        # ReAct loop: think → act (call tools) → observe (tool results) → repeat,
        # until the model answers with no tool calls, or we hit the safety cap.
        for _ in range(self.max_iters):
            # 1. Ask the model. It either answers, or requests tool calls.
            msg = self.client.chat(messages, tools=self.specs)
            content = msg.get("content", "") or ""
            tool_calls = msg.get("tool_calls") or []

            # Fallback: some models (e.g. llama3.2) emit a tool call as JSON in
            # the text instead of as native tool_calls. Recover those so the
            # tool actually runs rather than the model hallucinating a result.
            if not tool_calls and content:
                recovered = _parse_text_tool_calls(content, set(self.tools))
                if recovered:
                    tool_calls = recovered
                    content = ""  # it was a tool call, not a final answer

            # 2. Record the model's turn so it has full context next iteration.
            assistant_turn: dict = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_turn["tool_calls"] = tool_calls
            messages.append(assistant_turn)

            # 3. No tool calls → this is the final answer. Done.
            if not tool_calls:
                return content or last_text

            # Remember any text seen alongside tool calls as a last-resort answer.
            if content:
                last_text = content

            # 4. Run each requested tool and feed the result back as role="tool".
            for call in tool_calls:
                fn = call.get("function", {}) or {}
                tname = fn.get("name", "")
                args = fn.get("arguments", {})

                if on_event:
                    args_dict = args if isinstance(args, dict) else {}
                    on_event({
                        "type": "tool_call",
                        "agent": self.name,
                        "tool": tname,
                        "preview": _preview(args_dict),
                    })

                tool = self.tools.get(tname)
                result = tool.invoke(args) if tool else f"Error: unknown tool {tname!r}"

                if on_event:
                    on_event({"type": "tool_done", "agent": self.name, "tool": tname})

                # Ollama expects tool results as role="tool"; include the name
                # so models that track call/answer pairing can match them up.
                messages.append({"role": "tool", "name": tname, "content": result})

        # Iteration cap reached — make one final tool-free call so the model
        # must produce a text answer from everything it has gathered.
        final = self.client.chat(messages)
        return final.get("content", "") or last_text

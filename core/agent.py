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
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task},
        ]
        last_text = ""

        for _ in range(self.max_iters):
            msg = self.client.chat(messages, tools=self.specs)
            content = msg.get("content", "") or ""
            tool_calls = msg.get("tool_calls") or []

            # Preserve the assistant turn (with any tool calls) for context.
            assistant_turn: dict = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_turn["tool_calls"] = tool_calls
            messages.append(assistant_turn)

            if content:
                last_text = content

            if not tool_calls:
                return content or last_text

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

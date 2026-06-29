"""Minimal Ollama chat client — no LangChain.

Talks to Ollama's native HTTP API (`POST /api/chat`). Two modes:
  - chat()   : one non-streaming turn; supports tool-calling for models that
               implement it (llama3.1/3.2, qwen2.5, mistral-nemo, ...).
  - stream() : yields the assistant reply token-by-token (final answer only,
               no tools) so the UI can render the summary as it is written.

Config comes from the environment (set by config.load_config or the shell):
  OLLAMA_BASE_URL   default http://localhost:11434
  OLLAMA_MODEL      default llama3.2
  OLLAMA_ROUTER_MODEL  default = OLLAMA_MODEL (router only classifies)
"""
from __future__ import annotations

import json
import os
from typing import Any, Iterator

import httpx


def base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def default_model() -> str:
    return os.getenv("OLLAMA_MODEL", "llama3.2")


def router_model() -> str:
    # The router only classifies a request, so a small/fast model is plenty.
    # Defaults to the main model unless OLLAMA_ROUTER_MODEL overrides it.
    return os.getenv("OLLAMA_ROUTER_MODEL", default_model())


class OllamaError(RuntimeError):
    """Raised when Ollama is unreachable or returns an error status."""


class OllamaClient:
    def __init__(
        self,
        model: str | None = None,
        base_url_: str | None = None,
        timeout: float = 600.0,
    ):
        self.model = model or default_model()
        self.base_url = (base_url_ or base_url()).rstrip("/")
        self.timeout = timeout

    # ── non-streaming, tool-capable ──────────────────────────────────────────
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        fmt: str | dict | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> dict:
        """Run one chat turn. Returns the assistant message dict, e.g.
        {"role": "assistant", "content": "...", "tool_calls": [...]}."""
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,                 # one complete reply, not a token stream
        }
        if tools:
            payload["tools"] = tools         # tool specs the model may call
        if fmt is not None:
            payload["format"] = fmt          # "json" forces valid-JSON output
        if temperature is not None:
            payload["options"] = {"temperature": temperature}

        data = self._post("/api/chat", payload)
        # Response shape: {"message": {"role", "content", "tool_calls"?}, ...}
        return data.get("message", {}) or {}

    # ── streaming, text-only ─────────────────────────────────────────────────
    def stream(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
    ) -> Iterator[str]:
        """Yield the assistant reply token-by-token. No tools."""
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "stream": True,
        }
        if temperature is not None:
            payload["options"] = {"temperature": temperature}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as r:
                    r.raise_for_status()
                    # Ollama streams newline-delimited JSON: one object per line,
                    # each carrying a slice of the reply in message.content, with
                    # the final line marked done=true.
                    for line in r.iter_lines():
                        if not line:
                            continue
                        chunk = json.loads(line)
                        token = (chunk.get("message") or {}).get("content", "")
                        if token:
                            yield token
                        if chunk.get("done"):
                            break
        except httpx.HTTPStatusError as e:
            raise OllamaError(self._http_msg(e)) from e
        except httpx.RequestError as e:
            raise OllamaError(self._conn_msg(e)) from e

    # ── internals ────────────────────────────────────────────────────────────
    def _post(self, path: str, payload: dict) -> dict:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(f"{self.base_url}{path}", json=payload)
                r.raise_for_status()
                return r.json()
        except httpx.HTTPStatusError as e:
            raise OllamaError(self._http_msg(e)) from e
        except httpx.RequestError as e:
            raise OllamaError(self._conn_msg(e)) from e

    def _http_msg(self, e: httpx.HTTPStatusError) -> str:
        body = e.response.text[:300]
        return f"Ollama HTTP {e.response.status_code}: {body}"

    def _conn_msg(self, e: httpx.RequestError) -> str:
        return (
            f"Cannot reach Ollama at {self.base_url} ({e}). "
            f"Start it with `ollama serve` and pull the model "
            f"with `ollama pull {self.model}`."
        )

"""LLM access for Maybach — Ollama only, no API key required.

This is a thin convenience layer over core.llm. Everything runs against a local
Ollama server today; a cloud provider can be added later behind get_client()
without touching the agents or orchestrator.

    OLLAMA_BASE_URL   default http://localhost:11434
    OLLAMA_MODEL      default llama3.2
"""
from core.llm import OllamaClient, default_model, router_model  # re-exported


def get_client(model: str | None = None) -> OllamaClient:
    """Return an Ollama chat client. Pass `model` to override OLLAMA_MODEL."""
    return OllamaClient(model=model)


def message_text(content) -> str:
    """Normalise a chat message's content to plain text.

    Ollama returns content as a plain string; this also tolerates the list-of-
    typed-blocks shape some providers use, so callers never leak a raw repr
    into saved files or summaries.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type", "text") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(p for p in parts if p)
    return str(content)

import os
import warnings
from langchain_core.language_models import BaseChatModel


def get_llm(model: str | None = None) -> BaseChatModel:
    """
    Central LLM factory. All agents and the orchestrator call this instead of
    instantiating a provider directly, so switching providers is one env var.

    Args:
        model: Optional model ID override. Only applies to Bedrock — Ollama
               always uses OLLAMA_MODEL. Used by the orchestrator router to
               pin a cheaper model (Haiku) without affecting worker agents.
    """
    provider = os.getenv("LLM_PROVIDER", "bedrock").lower()

    if provider == "bedrock":
        # Fall back to Ollama if creds are missing so local dev works without
        # an AWS account. Explicit LLM_PROVIDER=ollama silences this warning.
        if not os.getenv("AWS_ACCESS_KEY_ID"):
            warnings.warn(
                "AWS_ACCESS_KEY_ID not set — falling back to Ollama. "
                "Set LLM_PROVIDER=ollama to silence this warning.",
                stacklevel=2,
            )
            provider = "ollama"
        else:
            from langchain_aws import ChatBedrockConverse
            return ChatBedrockConverse(
                model=model or os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250514-v1:0")
            )

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER: {provider!r}. Supported: bedrock, ollama"
    )


# Bedrock model ID for Claude Haiku — used by the orchestrator router.
# Routing only classifies tasks, so a small/fast model is sufficient and cheaper.
HAIKU = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

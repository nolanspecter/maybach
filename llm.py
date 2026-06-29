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
        region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        model_id = model or os.getenv(
            "BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
        )

        # 1. Automatic credential resolution first.
        # boto3's default credential chain resolves, in order: real env vars,
        # the shared profile (~/.aws/credentials), and — crucially for
        # SageMaker / EC2 / ECS — the attached IAM execution role via the
        # container or instance metadata endpoint. Letting boto3 resolve the
        # chain (instead of passing keys) also means temporary role credentials
        # are refreshed automatically before they expire.
        import boto3

        if boto3.Session(region_name=region).get_credentials() is not None:
            from langchain_aws import ChatBedrockConverse
            return ChatBedrockConverse(model=model_id, region_name=region)

        # 2. No ambient credentials — fall back to explicit keys from
        # config.yaml. These live in a private namespace (see config.py) so they
        # never shadow an execution role in the chain above.
        cfg_key = os.getenv("MAYBACH_AWS_ACCESS_KEY_ID")
        if cfg_key:
            from langchain_aws import ChatBedrockConverse
            kwargs = dict(
                model=model_id,
                region_name=region,
                aws_access_key_id=cfg_key,
                aws_secret_access_key=os.getenv("MAYBACH_AWS_SECRET_ACCESS_KEY"),
            )
            if os.getenv("MAYBACH_AWS_SESSION_TOKEN"):
                kwargs["aws_session_token"] = os.getenv("MAYBACH_AWS_SESSION_TOKEN")
            return ChatBedrockConverse(**kwargs)

        # 3. Nothing available — fall back to Ollama so local dev works without
        # an AWS account. Explicit LLM_PROVIDER=ollama silences this warning.
        warnings.warn(
            "No AWS credentials found (no execution role, shared profile, env "
            "vars, or config.yaml keys) — falling back to Ollama. "
            "Set LLM_PROVIDER=ollama to silence this warning.",
            stacklevel=2,
        )
        provider = "ollama"

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER: {provider!r}. Supported: bedrock, ollama"
    )


def message_text(content) -> str:
    """Normalise a chat message's content to plain text.

    Bedrock Converse returns content as a list of typed blocks
    (e.g. [{"type": "text", "text": "..."}]); Ollama returns a plain string.
    Without this, str(list) leaks the raw repr into saved files and summaries.
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


# Bedrock model ID for Claude Haiku — used by the orchestrator router.
# Routing only classifies tasks, so a small/fast model is sufficient and cheaper.
HAIKU = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
 
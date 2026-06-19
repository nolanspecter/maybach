"""
Loads config.yaml and sets environment variables so the rest of the codebase
(llm.py, agents) can read them via os.getenv() unchanged.

Precedence: existing env vars > config.yaml (os.environ.setdefault never
overwrites vars that are already set, so shell exports still take priority).
"""
import os
import yaml
from pathlib import Path


def load_config() -> None:
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        return

    with open(config_path) as f:
        cfg = yaml.safe_load(f) or {}

    llm = cfg.get("llm", {})
    if llm.get("provider"):
        os.environ.setdefault("LLM_PROVIDER", llm["provider"])

    bedrock = cfg.get("bedrock", {})
    if bedrock.get("access_key_id"):
        os.environ.setdefault("AWS_ACCESS_KEY_ID", bedrock["access_key_id"])
    if bedrock.get("secret_access_key"):
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", bedrock["secret_access_key"])
    if bedrock.get("region"):
        os.environ.setdefault("AWS_DEFAULT_REGION", bedrock["region"])
    if bedrock.get("model_id"):
        os.environ.setdefault("BEDROCK_MODEL_ID", bedrock["model_id"])
    if bedrock.get("session_token"):
        os.environ.setdefault("AWS_SESSION_TOKEN", bedrock["session_token"])

    ollama = cfg.get("ollama", {})
    if ollama.get("model"):
        os.environ.setdefault("OLLAMA_MODEL", ollama["model"])
    if ollama.get("base_url"):
        os.environ.setdefault("OLLAMA_BASE_URL", ollama["base_url"])

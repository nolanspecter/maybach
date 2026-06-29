"""
Loads config.yaml and exports settings as environment variables so the rest of
the codebase (core.llm, orchestrator) can read them via os.getenv() unchanged.

Precedence: existing env vars > config.yaml. os.environ.setdefault never
overwrites a var that is already set, so shell exports still win.

Ollama-only today — no API keys, no cloud credentials. Example config.yaml:

    ollama:
      model: llama3.2
      base_url: http://localhost:11434
      router_model: llama3.2     # optional; defaults to `model`
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

    ollama = cfg.get("ollama", {})
    if ollama.get("model"):
        os.environ.setdefault("OLLAMA_MODEL", ollama["model"])
    if ollama.get("base_url"):
        os.environ.setdefault("OLLAMA_BASE_URL", ollama["base_url"])
    if ollama.get("router_model"):
        os.environ.setdefault("OLLAMA_ROUTER_MODEL", ollama["router_model"])

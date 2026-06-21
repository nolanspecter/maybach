"""
Loads config.yaml and sets environment variables so the rest of the codebase
(llm.py, agents) can read them via os.getenv() unchanged.

Precedence: existing env vars > config.yaml (os.environ.setdefault never
overwrites vars that are already set, so shell exports still take priority).

Credential note: AWS keys from config.yaml are stored under a private MAYBACH_*
namespace, not the standard AWS_* names. This keeps them out of boto3's default
credential chain so that automatic credentials (a SageMaker/EC2 execution role,
an ~/.aws profile, or real shell env vars) always take priority. llm.py only
falls back to the config.yaml keys when the automatic chain resolves nothing.
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
    # Credentials from config.yaml are a *fallback* only. They go into a private
    # MAYBACH_* namespace so they do NOT enter boto3's default credential chain
    # and therefore can never shadow ambient credentials — a SageMaker/EC2/ECS
    # execution role, an ~/.aws profile, or real shell env vars. llm.py prefers
    # the automatic chain and only uses these keys if nothing else resolves.
    if bedrock.get("access_key_id"):
        os.environ.setdefault("MAYBACH_AWS_ACCESS_KEY_ID", bedrock["access_key_id"])
    if bedrock.get("secret_access_key"):
        os.environ.setdefault("MAYBACH_AWS_SECRET_ACCESS_KEY", bedrock["secret_access_key"])
    if bedrock.get("session_token"):
        os.environ.setdefault("MAYBACH_AWS_SESSION_TOKEN", bedrock["session_token"])
    # Region and model id are not credentials — safe under their standard names.
    if bedrock.get("region"):
        os.environ.setdefault("AWS_DEFAULT_REGION", bedrock["region"])
    if bedrock.get("model_id"):
        os.environ.setdefault("BEDROCK_MODEL_ID", bedrock["model_id"])

    ollama = cfg.get("ollama", {})
    if ollama.get("model"):
        os.environ.setdefault("OLLAMA_MODEL", ollama["model"])
    if ollama.get("base_url"):
        os.environ.setdefault("OLLAMA_BASE_URL", ollama["base_url"])
 
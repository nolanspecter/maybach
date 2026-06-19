"""
Virtual Software Engineer (vSWE) — writes and validates code.

Tools available:
  run_python — write and execute Python, verify output before responding
  run_bash   — inspect the environment, check files, run shell commands
  write_file — save code/scripts to shared workspace
  read_file  — read specs or data other agents wrote
  list_files — see what's in the shared workspace
"""
import uuid
from langgraph.prebuilt import create_react_agent

from llm import get_llm
from tools.code_tools import run_python, run_bash
from tools.workspace_tools import write_file, read_file, list_files, _workspace

SYSTEM_PROMPT = """You are a Virtual Software Engineer (vSWE).
Your job: write clean, working code to solve engineering tasks.
Always run your code to verify it works before responding.
Prefer Python. Use bash only for file system or env inspection.
Return the final code in a fenced block along with test output."""

_llm = get_llm()
_tools = [run_python, run_bash, write_file, read_file, list_files]

agent = create_react_agent(_llm, _tools, prompt=SYSTEM_PROMPT)


def run(task: str, config: dict | None = None) -> str:
    result = agent.invoke({"messages": [("human", task)]}, config=config)
    content = result["messages"][-1].content
    filename = f"vswe_{uuid.uuid4().hex[:8]}.md"
    (_workspace() / filename).write_text(content, encoding="utf-8")
    return f"workspace/{filename}"

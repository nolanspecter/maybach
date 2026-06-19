"""
Virtual Software Engineer (vSWE) — writes and validates code.

Tools available:
  run_python — write and execute Python, verify output before responding
  run_bash   — inspect the environment, check files, run shell commands
"""
from langgraph.prebuilt import create_react_agent

from llm import get_llm
from tools.code_tools import run_python, run_bash

SYSTEM_PROMPT = """You are a Virtual Software Engineer (vSWE).
Your job: write clean, working code to solve engineering tasks.
Always run your code to verify it works before responding.
Prefer Python. Use bash only for file system or env inspection.
Return the final code in a fenced block along with test output."""

_llm = get_llm()
_tools = [run_python, run_bash]

agent = create_react_agent(_llm, _tools, prompt=SYSTEM_PROMPT)


def run(task: str, config: dict | None = None) -> str:
    result = agent.invoke({"messages": [("human", task)]}, config=config)
    return result["messages"][-1].content

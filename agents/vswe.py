"""Virtual Software Engineer — writes and executes code."""
import os
from langchain_aws import ChatBedrockConverse
from langgraph.prebuilt import create_react_agent

from tools.code_tools import run_python, run_bash

MODEL = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250514-v1:0")

SYSTEM_PROMPT = """You are a Virtual Software Engineer (vSWE).
Your job: write clean, working code to solve engineering tasks.
Always run your code to verify it works before responding.
Prefer Python. Use bash only for file system or env inspection.
Return the final code in a fenced block along with test output."""

_llm = ChatBedrockConverse(model=MODEL)
_tools = [run_python, run_bash]

agent = create_react_agent(_llm, _tools, prompt=SYSTEM_PROMPT)


def run(task: str, config: dict | None = None) -> str:
    result = agent.invoke({"messages": [("human", task)]}, config=config)
    return result["messages"][-1].content

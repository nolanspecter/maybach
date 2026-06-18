"""Virtual Data Analyst — queries data, produces tables and insights."""
import os
from langchain_aws import ChatBedrockConverse
from langgraph.prebuilt import create_react_agent

from tools.sql_tools import run_sql, list_tables, describe_table
from tools.code_tools import run_python

MODEL = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250514-v1:0")

SYSTEM_PROMPT = """You are a Virtual Data Analyst (vDA).
Your job: answer data questions by querying databases and running analysis code.
Always show your SQL or Python before running it.
Return results as markdown tables when possible.
Be concise — lead with the answer, then show supporting data."""

_llm = ChatBedrockConverse(model=MODEL)
_tools = [run_sql, list_tables, describe_table, run_python]

agent = create_react_agent(_llm, _tools, prompt=SYSTEM_PROMPT)


def run(task: str, config: dict | None = None) -> str:
    result = agent.invoke({"messages": [("human", task)]}, config=config)
    return result["messages"][-1].content

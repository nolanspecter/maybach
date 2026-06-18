"""Virtual Data Scientist — builds models, runs statistical analysis, interprets results."""
import os
from langchain_aws import ChatBedrockConverse
from langgraph.prebuilt import create_react_agent

from tools.code_tools import run_python
from tools.sql_tools import run_sql, list_tables
from tools.research_tools import summarize_findings

MODEL = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250514-v1:0")

SYSTEM_PROMPT = """You are a Virtual Data Scientist (vDS).
Your job: design and run data science workflows — feature engineering, model training,
statistical tests, and result interpretation.
Always show code and output. Interpret numbers in plain English.
Use Python (pandas, sklearn, scipy, numpy) for analysis."""

_llm = ChatBedrockConverse(model=MODEL)
_tools = [run_python, run_sql, list_tables, summarize_findings]

agent = create_react_agent(_llm, _tools, prompt=SYSTEM_PROMPT)


def run(task: str, config: dict | None = None) -> str:
    result = agent.invoke({"messages": [("human", task)]}, config=config)
    return result["messages"][-1].content

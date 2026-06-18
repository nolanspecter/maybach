"""Virtual Data Scientist — builds models, runs statistical analysis, interprets results."""
from langgraph.prebuilt import create_react_agent

from llm import get_llm
from tools.code_tools import run_python
from tools.sql_tools import run_sql, list_tables
from tools.research_tools import summarize_findings

SYSTEM_PROMPT = """You are a Virtual Data Scientist (vDS).
Your job: design and run data science workflows — feature engineering, model training,
statistical tests, and result interpretation.
Always show code and output. Interpret numbers in plain English.
Use Python (pandas, sklearn, scipy, numpy) for analysis."""

_llm = get_llm()
_tools = [run_python, run_sql, list_tables, summarize_findings]

agent = create_react_agent(_llm, _tools, prompt=SYSTEM_PROMPT)


def run(task: str, config: dict | None = None) -> str:
    result = agent.invoke({"messages": [("human", task)]}, config=config)
    return result["messages"][-1].content

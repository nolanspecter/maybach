"""
Virtual Data Scientist (vDS) — ML modelling, statistical analysis, and interpretation.

Tools available:
  run_python        — train models, run stats (pandas, sklearn, scipy, numpy)
  run_sql           — pull raw data before analysis
  list_tables       — discover available data sources
  summarize_findings — compile results into a structured narrative
  write_file        — save models, results, or reports to shared workspace
  read_file         — read datasets or specs other agents wrote
  list_files        — see what's in the shared workspace
"""
from langgraph.prebuilt import create_react_agent

from llm import get_llm
from tools.code_tools import run_python
from tools.sql_tools import run_sql, list_tables
from tools.research_tools import summarize_findings
from tools.workspace_tools import write_file, read_file, list_files

SYSTEM_PROMPT = """You are a Virtual Data Scientist (vDS).
Your job: design and run data science workflows — feature engineering, model training,
statistical tests, and result interpretation.
Always show code and output. Interpret numbers in plain English.
Use Python (pandas, sklearn, scipy, numpy) for analysis.
Use write_file to save datasets, model outputs, or reports for other agents."""

_llm = get_llm()
_tools = [run_python, run_sql, list_tables, summarize_findings, write_file, read_file, list_files]

agent = create_react_agent(_llm, _tools, prompt=SYSTEM_PROMPT)


def run(task: str, config: dict | None = None) -> str:
    result = agent.invoke({"messages": [("human", task)]}, config=config)
    return result["messages"][-1].content

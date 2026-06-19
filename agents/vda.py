"""
Virtual Data Analyst (vDA) — answers data questions via SQL and Python.

Tools available:
  run_sql        — execute queries against a SQLite database
  list_tables    — discover what tables exist
  describe_table — inspect a table's schema before querying
  run_python     — run analysis code (pandas, matplotlib, etc.)
  write_file     — save reports/data to shared workspace
  read_file      — read files other agents wrote
  list_files     — see what's in the shared workspace
"""
from langgraph.prebuilt import create_react_agent

from llm import get_llm
from tools.sql_tools import run_sql, list_tables, describe_table
from tools.code_tools import run_python
from tools.workspace_tools import write_file, read_file, list_files

SYSTEM_PROMPT = """You are a Virtual Data Analyst (vDA).
Your job: answer data questions by querying databases and running analysis code.
Always show your SQL or Python before running it.
Return results as markdown tables when possible.
Be concise — lead with the answer, then show supporting data.
Use write_file to save reports or datasets for other agents to use."""

_llm = get_llm()
_tools = [run_sql, list_tables, describe_table, run_python, write_file, read_file, list_files]

agent = create_react_agent(_llm, _tools, prompt=SYSTEM_PROMPT)


def run(task: str, config: dict | None = None) -> str:
    result = agent.invoke({"messages": [("human", task)]}, config=config)
    return result["messages"][-1].content

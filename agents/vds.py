"""
Virtual Data Scientist (vDS) — ML modelling, statistical analysis, and interpretation.

Tools available:
  run_python        — train models, run stats (pandas, sklearn, scipy, numpy)
  run_sql           — pull raw data before analysis
  list_tables       — discover available data sources
  summarize_findings — compile results into a structured narrative
  write_file        — save intermediate results to avoid context loss (cleaned up after run)
  read_file         — read datasets or specs other agents wrote
  list_files        — see what's in the shared workspace
"""
import uuid
from langgraph.prebuilt import create_react_agent

from llm import get_llm
from tools.code_tools import run_python
from tools.sql_tools import run_sql, list_tables
from tools.research_tools import summarize_findings
from tools.workspace_tools import write_file, read_file, list_files, _workspace

SYSTEM_PROMPT = """You are a Virtual Data Scientist (vDS).
Your job: design and run data science workflows — feature engineering, model training,
statistical tests, and result interpretation.
Always show code and output. Interpret numbers in plain English.
Use Python (pandas, sklearn, scipy, numpy) for analysis."""

_llm = get_llm()
_tools = [run_python, run_sql, list_tables, summarize_findings, write_file, read_file, list_files]

agent = create_react_agent(_llm, _tools, prompt=SYSTEM_PROMPT)


def run(task: str, config: dict | None = None) -> str:
    ws = _workspace()
    before = set(ws.iterdir())

    result = agent.invoke({"messages": [("human", task)]}, config=config)
    raw = result["messages"][-1].content
    content = raw if isinstance(raw, str) else str(raw)

    filename = f"vds_{uuid.uuid4().hex[:8]}.md"
    final = ws / filename
    final.write_text(content, encoding="utf-8")

    for p in set(ws.iterdir()) - before - {final}:
        p.unlink(missing_ok=True)

    return f"workspace/{filename}"

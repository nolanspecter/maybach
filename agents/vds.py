"""
Virtual Data Scientist (vDS) — ML modelling, statistical analysis, and interpretation.

Tools available:
  run_python        — train models, run stats (pandas, sklearn, scipy, numpy)
  run_sql           — pull raw data before analysis
  list_tables       — discover available data sources
  summarize_findings — compile results into a structured narrative
  write_file        — save deliverable files (kept after run)
  save_checkpoint   — save scratch mid-work to avoid context loss (cleaned up after run)
  read_file         — read datasets or specs other agents wrote
  list_files        — see what's in the shared workspace
"""
import uuid

from core.agent import Agent
from tools.code_tools import run_python
from tools.sql_tools import run_sql, list_tables
from tools.research_tools import summarize_findings
from tools.workspace_tools import (
    write_file, save_checkpoint, read_file, list_files,
    _workspace, cleanup_checkpoints,
)

SYSTEM_PROMPT = """You are a Virtual Data Scientist (vDS).
Your job: design and run data science workflows — feature engineering, model training,
statistical tests, and result interpretation.
Always show code and output. Interpret numbers in plain English.
Use Python (pandas, sklearn, scipy, numpy) for analysis."""

agent = Agent(
    name="vDS",
    system_prompt=SYSTEM_PROMPT,
    tools=[run_python, run_sql, list_tables, summarize_findings,
           write_file, save_checkpoint, read_file, list_files],
)


def run(task: str, on_event=None) -> str:
    """Run the agent and save its final answer as the deliverable summary.
    Returns the workspace-relative path. on_event streams tool activity."""
    content = agent.run(task, on_event=on_event)

    filename = f"vds_{uuid.uuid4().hex[:8]}.md"
    (_workspace() / filename).write_text(content, encoding="utf-8")

    cleanup_checkpoints()

    return f"workspace/{filename}"

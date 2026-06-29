"""
Virtual Data Analyst (vDA) — answers data questions via SQL and Python.

Tools available:
  run_sql        — execute queries against a SQLite database
  list_tables    — discover what tables exist
  describe_table — inspect a table's schema before querying
  run_python     — run analysis code (pandas, matplotlib, etc.)
  write_file     — save deliverable files (kept after run)
  save_checkpoint — save scratch mid-work to avoid context loss (cleaned up after run)
  read_file      — read files other agents wrote
  list_files     — see what's in the shared workspace
"""
import uuid

from core.agent import Agent
from tools.sql_tools import run_sql, list_tables, describe_table
from tools.code_tools import run_python
from tools.workspace_tools import (
    write_file, save_checkpoint, read_file, list_files,
    _workspace, cleanup_checkpoints,
)

SYSTEM_PROMPT = """You are a Virtual Data Analyst (vDA).
Your job: answer data questions by querying databases and running analysis code.
Always show your SQL or Python before running it.
Return results as markdown tables when possible.
Be concise — lead with the answer, then show supporting data."""

agent = Agent(
    name="vDA",
    system_prompt=SYSTEM_PROMPT,
    tools=[run_sql, list_tables, describe_table, run_python,
           write_file, save_checkpoint, read_file, list_files],
)


def run(task: str, on_event=None) -> str:
    """Run the agent and save its final answer as the deliverable summary.
    Returns the workspace-relative path. on_event streams tool activity."""
    content = agent.run(task, on_event=on_event)

    filename = f"vda_{uuid.uuid4().hex[:8]}.md"
    (_workspace() / filename).write_text(content, encoding="utf-8")

    # Purge only scratch checkpoints — deliverables the agent wrote are kept.
    cleanup_checkpoints()

    return f"workspace/{filename}"

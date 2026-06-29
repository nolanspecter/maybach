"""
Virtual Software Engineer (vSWE) — writes and validates code.

Tools available:
  run_python — write and execute Python, verify output before responding
  run_bash   — inspect the environment, check files, run shell commands
  write_file — save deliverable files (kept after run)
  save_checkpoint — save scratch mid-work to avoid context loss (cleaned up after run)
  read_file  — read specs or data other agents wrote
  list_files — see what's in the shared workspace
"""
from core.agent import Agent
from core.output import deliverable_snapshot, salvage_deliverables, write_job_output
from tools.code_tools import run_python, run_bash
from tools.workspace_tools import (
    write_file, save_checkpoint, read_file, list_files, cleanup_checkpoints,
)

SYSTEM_PROMPT = """You are a Virtual Software Engineer (vSWE).
Your job: write clean, working code to solve engineering tasks.
Always run your code to verify it works before responding.
Prefer Python. Use bash only for file system or env inspection.

When the task asks you to PRODUCE a file or artifact (an HTML page, a script,
a CSV, a config), you MUST save it with the write_file tool using a real,
descriptive filename (e.g. index.html, app.py) — that saved file is the
deliverable. Do not only paste it in your reply. After saving, state the
filename you wrote.

Return a short summary of what you built plus the final code in a fenced block
along with test output."""

agent = Agent(
    name="vSWE",
    system_prompt=SYSTEM_PROMPT,
    tools=[run_python, run_bash, write_file, save_checkpoint, read_file, list_files],
)


def run(task: str, on_event=None) -> str:
    """Run the agent. Always writes the job result to a file and returns its
    path. If the model emitted code but never saved it, salvage it as a real
    deliverable. on_event streams tool activity."""
    before = deliverable_snapshot()
    content = agent.run(task, on_event=on_event)

    salvage_deliverables("vSWE", content, before)
    path = write_job_output("vSWE", content)

    cleanup_checkpoints()
    return path

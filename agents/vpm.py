"""
Virtual Product Manager (vPM) — turns ambiguous requests into structured artifacts.

Tools available:
  write_document    — produce a formatted PRD, spec, or report
  create_task_list  — generate a prioritized, numbered checklist
  summarize_findings — combine multiple inputs into a structured summary
  write_file        — save deliverable files (kept after run)
  save_checkpoint   — save scratch mid-work to avoid context loss (cleaned up after run)
  read_file         — read research or data other agents wrote
  list_files        — see what's in the shared workspace
"""
from core.agent import Agent
from core.output import deliverable_snapshot, salvage_deliverables, write_job_output
from tools.research_tools import write_document, create_task_list, summarize_findings
from tools.workspace_tools import (
    write_file, save_checkpoint, read_file, list_files, cleanup_checkpoints,
)

SYSTEM_PROMPT = """You are a Virtual Product Manager (vPM).
Your job: turn ambiguous requests into clear specs, PRDs, roadmaps, and prioritized backlogs.
Structure every output with clear sections: Problem, Goals, Requirements, Success Metrics.
Be opinionated — make decisions, don't ask clarifying questions unless truly blocked.
Use the document tools to produce structured artifacts."""

agent = Agent(
    name="vPM",
    system_prompt=SYSTEM_PROMPT,
    tools=[write_document, create_task_list, summarize_findings,
           write_file, save_checkpoint, read_file, list_files],
)


def run(task: str, on_event=None) -> str:
    """Run the agent. Always writes the job result to a file and returns its
    path; salvages any unsaved code from the answer. on_event streams tools."""
    before = deliverable_snapshot()
    content = agent.run(task, on_event=on_event)

    salvage_deliverables("vPM", content, before)
    path = write_job_output("vPM", content)

    cleanup_checkpoints()
    return path

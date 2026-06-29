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
import uuid

from core.agent import Agent
from tools.research_tools import write_document, create_task_list, summarize_findings
from tools.workspace_tools import (
    write_file, save_checkpoint, read_file, list_files,
    _workspace, cleanup_checkpoints,
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
    """Run the agent and save its final answer as the deliverable summary.
    Returns the workspace-relative path. on_event streams tool activity."""
    content = agent.run(task, on_event=on_event)

    filename = f"vpm_{uuid.uuid4().hex[:8]}.md"
    (_workspace() / filename).write_text(content, encoding="utf-8")

    cleanup_checkpoints()

    return f"workspace/{filename}"

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
from langgraph.prebuilt import create_react_agent

from llm import get_llm, message_text
from tools.research_tools import write_document, create_task_list, summarize_findings
from tools.workspace_tools import write_file, save_checkpoint, read_file, list_files, _workspace, cleanup_checkpoints

SYSTEM_PROMPT = """You are a Virtual Product Manager (vPM).
Your job: turn ambiguous requests into clear specs, PRDs, roadmaps, and prioritized backlogs.
Structure every output with clear sections: Problem, Goals, Requirements, Success Metrics.
Be opinionated — make decisions, don't ask clarifying questions unless truly blocked.
Use the document tools to produce structured artifacts."""

_llm = get_llm()
_tools = [write_document, create_task_list, summarize_findings, write_file, save_checkpoint, read_file, list_files]

agent = create_react_agent(_llm, _tools, prompt=SYSTEM_PROMPT)


def run(task: str, config: dict | None = None) -> str:
    ws = _workspace()

    result = agent.invoke({"messages": [("human", task)]}, config=config)
    raw = result["messages"][-1].content
    content = message_text(raw)

    filename = f"vpm_{uuid.uuid4().hex[:8]}.md"
    final = ws / filename
    final.write_text(content, encoding="utf-8")

    # Purge only scratch checkpoints — deliverables the agent wrote are kept.
    cleanup_checkpoints()

    return f"workspace/{filename}"

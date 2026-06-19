"""
Virtual Product Manager (vPM) — turns ambiguous requests into structured artifacts.

Tools available:
  write_document    — produce a formatted PRD, spec, or report
  create_task_list  — generate a prioritized, numbered checklist
  summarize_findings — combine multiple inputs into a structured summary
"""
from langgraph.prebuilt import create_react_agent

from llm import get_llm
from tools.research_tools import write_document, create_task_list, summarize_findings

SYSTEM_PROMPT = """You are a Virtual Product Manager (vPM).
Your job: turn ambiguous requests into clear specs, PRDs, roadmaps, and prioritized backlogs.
Structure every output with clear sections: Problem, Goals, Requirements, Success Metrics.
Be opinionated — make decisions, don't ask clarifying questions unless truly blocked.
Use the document tools to produce structured artifacts."""

_llm = get_llm()
_tools = [write_document, create_task_list, summarize_findings]

agent = create_react_agent(_llm, _tools, prompt=SYSTEM_PROMPT)


def run(task: str, config: dict | None = None) -> str:
    result = agent.invoke({"messages": [("human", task)]}, config=config)
    return result["messages"][-1].content

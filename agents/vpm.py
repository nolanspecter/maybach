"""Virtual Product Manager — writes PRDs, specs, roadmaps, and task breakdowns."""
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from tools.research_tools import write_document, create_task_list, summarize_findings

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a Virtual Product Manager (vPM).
Your job: turn ambiguous requests into clear specs, PRDs, roadmaps, and prioritized backlogs.
Structure every output with clear sections: Problem, Goals, Requirements, Success Metrics.
Be opinionated — make decisions, don't ask clarifying questions unless truly blocked.
Use the document tools to produce structured artifacts."""

_llm = ChatAnthropic(model=MODEL)
_tools = [write_document, create_task_list, summarize_findings]

agent = create_react_agent(_llm, _tools, prompt=SYSTEM_PROMPT)


def run(task: str, config: dict | None = None) -> str:
    result = agent.invoke({"messages": [("human", task)]}, config=config)
    return result["messages"][-1].content

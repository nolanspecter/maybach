"""Virtual Product Manager — writes PRDs, specs, roadmaps, and task breakdowns."""
import os
from langchain_aws import ChatBedrockConverse
from langgraph.prebuilt import create_react_agent

from tools.research_tools import write_document, create_task_list, summarize_findings

MODEL = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250514-v1:0")

SYSTEM_PROMPT = """You are a Virtual Product Manager (vPM).
Your job: turn ambiguous requests into clear specs, PRDs, roadmaps, and prioritized backlogs.
Structure every output with clear sections: Problem, Goals, Requirements, Success Metrics.
Be opinionated — make decisions, don't ask clarifying questions unless truly blocked.
Use the document tools to produce structured artifacts."""

_llm = ChatBedrockConverse(model=MODEL)
_tools = [write_document, create_task_list, summarize_findings]

agent = create_react_agent(_llm, _tools, prompt=SYSTEM_PROMPT)


def run(task: str, config: dict | None = None) -> str:
    result = agent.invoke({"messages": [("human", task)]}, config=config)
    return result["messages"][-1].content

"""Maybach core — a small, dependency-light agent harness.

No LangChain, no LangGraph. Three pieces:
  - llm.py    : an Ollama HTTP chat client (tool-calling + token streaming)
  - tools.py  : a @tool decorator that turns a typed function into a tool spec
  - agent.py  : a ReAct loop that runs tools until the model gives a final answer
"""

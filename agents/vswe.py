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
import uuid
from langgraph.prebuilt import create_react_agent

from llm import get_llm, message_text
from tools.code_tools import run_python, run_bash
from tools.workspace_tools import write_file, save_checkpoint, read_file, list_files, _workspace, cleanup_checkpoints

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

_llm = get_llm()
_tools = [run_python, run_bash, write_file, save_checkpoint, read_file, list_files]

agent = create_react_agent(_llm, _tools, prompt=SYSTEM_PROMPT)


def run(task: str, config: dict | None = None) -> str:
    ws = _workspace()

    result = agent.invoke({"messages": [("human", task)]}, config=config)
    raw = result["messages"][-1].content
    content = message_text(raw)

    filename = f"vswe_{uuid.uuid4().hex[:8]}.md"
    final = ws / filename
    final.write_text(content, encoding="utf-8")

    # Purge only scratch checkpoints — deliverables the agent wrote are kept.
    cleanup_checkpoints()

    return f"workspace/{filename}"

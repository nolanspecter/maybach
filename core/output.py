"""Guarantee every worker job produces a file — and rescue code artifacts.

Two guarantees the orchestrator relies on:

  1. write_job_output() ALWAYS writes a non-empty `<label>_<hex>.md` and returns
     its path. This is how the orchestrator knows a worker finished and what it
     produced, even if the model wrote nothing else.

  2. salvage_deliverables() rescues code the model put in fenced blocks but never
     saved via write_file, so a requested artifact (e.g. fib.py) still lands as a
     real, downloadable file instead of being trapped in the chat text.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from tools.workspace_tools import _workspace, _CHECKPOINT_DIR

# Internal per-job summary files — not user deliverables.
_SUMMARY_RE = re.compile(r"^v(?:da|pm|swe|ds)_[0-9a-f]+\.md$", re.IGNORECASE)
_FENCE_RE = re.compile(r"```([\w.+-]*)[ \t]*\n(.*?)```", re.DOTALL)
_FILENAME_RE = re.compile(r"[\w./-]+\.[A-Za-z0-9]{1,5}")

# Fenced languages we treat as saveable code. Plain/`text` blocks are skipped so
# console output and tables are never mistaken for deliverables.
_LANG_EXT = {
    "python": "py", "py": "py",
    "javascript": "js", "js": "js", "jsx": "jsx",
    "typescript": "ts", "ts": "ts", "tsx": "tsx",
    "html": "html", "css": "css",
    "bash": "sh", "sh": "sh", "shell": "sh",
    "sql": "sql", "json": "json",
    "yaml": "yml", "yml": "yml",
    "go": "go", "rust": "rs", "java": "java",
    "c": "c", "cpp": "cpp",
}

# Conventional default filename for an unnamed block of a given type.
_DEFAULT_NAME = {"html": "index.html"}


def deliverable_snapshot(ws: Path | None = None) -> set[str]:
    """Workspace-relative paths of current deliverables (excludes summaries
    and scratch checkpoints)."""
    ws = ws or _workspace()
    out: set[str] = set()
    for p in ws.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ws)
        if _CHECKPOINT_DIR in rel.parts or _SUMMARY_RE.match(rel.name):
            continue
        out.add(str(rel))
    return out


def _code_blocks(content: str):
    """Yield (ext, code) for each fenced block in a recognised code language."""
    for lang, body in _FENCE_RE.findall(content):
        ext = _LANG_EXT.get(lang.strip().lower())
        if ext and body.strip():
            yield ext, body.strip("\n")


def salvage_deliverables(label: str, content: str, before: set[str]) -> list[str]:
    """If the agent created no deliverable during its run, save the code blocks
    from its final answer as files. Returns the workspace-relative paths written.

    Skipped entirely when the model already wrote a deliverable via write_file —
    we trust an explicit save over salvage.
    """
    ws = _workspace()
    if deliverable_snapshot(ws) - before:
        return []

    blocks = list(_code_blocks(content))
    if not blocks:
        return []

    # Prefer a filename the model named in its answer (e.g. "save as fib.py").
    mentioned = _FILENAME_RE.findall(content)
    used: set[str] = set()
    written: list[str] = []
    for i, (ext, code) in enumerate(blocks, 1):
        name = None
        for m in mentioned:
            base = m.split("/")[-1]
            if base.lower().endswith("." + ext) and base not in used:
                name = base
                break
        if not name:
            # A web page should land as index.html so the UI can preview/visit it.
            default = _DEFAULT_NAME.get(ext)
            name = default if default and default not in used else f"{label.lower()}_output{i}.{ext}"
        used.add(name)
        try:
            (ws / name).write_text(code + "\n", encoding="utf-8")
            written.append(name)
        except OSError:
            continue
    return written


def write_job_output(label: str, content: str) -> str:
    """Always write the job's result to a summary file and return its path.
    Guarantees a non-empty file so the orchestrator always has something to read."""
    text = content if isinstance(content, str) else str(content)
    if not text.strip():
        text = f"[{label}] completed but produced no text output."
    filename = f"{label.lower()}_{uuid.uuid4().hex[:8]}.md"
    (_workspace() / filename).write_text(text, encoding="utf-8")
    return f"workspace/{filename}"

"""
Shared workspace tools — all agents read/write to the same folder.
Default path: ./workspace/ (relative to project root).
Override via WORKSPACE_DIR env var.
"""
import os
from pathlib import Path
from langchain_core.tools import tool

_CHECKPOINT_DIR = ".checkpoints"


def _workspace() -> Path:
    path = Path(os.getenv("WORKSPACE_DIR", "workspace"))
    path.mkdir(exist_ok=True)
    return path


@tool
def write_file(filename: str, content: str) -> str:
    """Write a deliverable file to the shared workspace (e.g. index.html, report.csv).

    Use this for any file that is part of the answer — it persists after the task.
    For throwaway scratch you only need mid-task, use save_checkpoint instead.
    Overwrites if exists.
    """
    try:
        path = _workspace() / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Written: workspace/{filename} ({len(content)} chars)"
    except Exception as e:
        return f"Error: {e}"


@tool
def save_checkpoint(filename: str, content: str) -> str:
    """Save an intermediate scratch file to avoid context loss mid-task.

    Checkpoints are auto-deleted when the task finishes — never use this for
    deliverables the user asked for (use write_file for those). Read a
    checkpoint back with read_file(".checkpoints/<filename>"). Overwrites if exists.
    """
    try:
        path = _workspace() / _CHECKPOINT_DIR / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Checkpoint saved: {_CHECKPOINT_DIR}/{filename} ({len(content)} chars)"
    except Exception as e:
        return f"Error: {e}"


def cleanup_checkpoints() -> None:
    """Delete the per-task checkpoint scratch dir. Deliverables are never touched."""
    import shutil
    ckpt = _workspace() / _CHECKPOINT_DIR
    if ckpt.exists():
        shutil.rmtree(ckpt, ignore_errors=True)


@tool
def read_file(filename: str) -> str:
    """Read a file from the shared workspace."""
    try:
        path = _workspace() / filename
        if not path.exists():
            return f"File not found: workspace/{filename}"
        return path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error: {e}"


@tool
def list_files(subdir: str = "") -> str:
    """List all files in the shared workspace (or a subdirectory)."""
    try:
        base = _workspace() / subdir if subdir else _workspace()
        if not base.exists():
            return "No files in workspace."
        files = [
            str(p.relative_to(_workspace()))
            for p in base.rglob("*")
            if p.is_file() and _CHECKPOINT_DIR not in p.parts
        ]
        return "\n".join(sorted(files)) if files else "No files in workspace."
    except Exception as e:
        return f"Error: {e}"

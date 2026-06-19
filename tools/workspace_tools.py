"""
Shared workspace tools — all agents read/write to the same folder.
Default path: ./workspace/ (relative to project root).
Override via WORKSPACE_DIR env var.
"""
import os
from pathlib import Path
from langchain_core.tools import tool

def _workspace() -> Path:
    path = Path(os.getenv("WORKSPACE_DIR", "workspace"))
    path.mkdir(exist_ok=True)
    return path


@tool
def write_file(filename: str, content: str) -> str:
    """Write content to a file in the shared workspace. Overwrites if exists."""
    try:
        path = _workspace() / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Written: workspace/{filename} ({len(content)} chars)"
    except Exception as e:
        return f"Error: {e}"


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
        files = [str(p.relative_to(_workspace())) for p in base.rglob("*") if p.is_file()]
        return "\n".join(sorted(files)) if files else "No files in workspace."
    except Exception as e:
        return f"Error: {e}"

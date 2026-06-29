from core.tools import tool


@tool
def write_document(title: str, content: str) -> str:
    """Write a structured document (PRD, spec, report, etc.) and return it formatted."""
    divider = "=" * 60
    return f"{divider}\n{title.upper()}\n{divider}\n\n{content}\n\n{divider}"


@tool
def create_task_list(tasks: list[str]) -> str:
    """Format a list of tasks as a numbered checklist."""
    if not tasks:
        return "No tasks provided."
    lines = [f"{i+1}. [ ] {task}" for i, task in enumerate(tasks)]
    return "\n".join(lines)


@tool
def summarize_findings(findings: list[str], title: str = "Summary") -> str:
    """Combine multiple findings into a structured summary."""
    if not findings:
        return "No findings to summarize."
    bullets = "\n".join(f"- {f}" for f in findings)
    return f"## {title}\n\n{bullets}"

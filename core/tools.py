"""A tiny tool framework — turn a typed Python function into a model tool.

`@tool` introspects a function's signature, type hints, and docstring to build
an Ollama/OpenAI-style tool spec, and wraps it so the agent loop can call it by
name with a dict of arguments.

    @tool
    def run_sql(query: str, db_path: str = ":memory:") -> str:
        '''Execute a SQL query and return results as a markdown table.'''
        ...

    run_sql.spec            # -> {"type": "function", "function": {...}}
    run_sql.invoke({"query": "SELECT 1"})   # -> "..."
"""
from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from typing import Any, Callable, get_args, get_origin, get_type_hints

_PY_TO_JSON = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _json_type(annotation: Any) -> dict:
    """Map a Python type annotation to a JSON-schema fragment."""
    origin = get_origin(annotation)
    if origin in (list, tuple):
        args = get_args(annotation)
        item = args[0] if args else str
        return {"type": "array", "items": {"type": _PY_TO_JSON.get(item, "string")}}
    if annotation in _PY_TO_JSON:
        return {"type": _PY_TO_JSON[annotation]}
    # Optional[X], unions, or anything unknown — a string is the safe default.
    return {"type": "string"}


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict          # JSON schema for the function arguments
    func: Callable[..., Any]

    @property
    def spec(self) -> dict:
        """Ollama / OpenAI function-tool spec."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def invoke(self, args: dict | str) -> str:
        """Run the tool. Never raises — errors come back as text so the model
        can read them and recover on the next turn."""
        if isinstance(args, str):
            try:
                args = json.loads(args) if args.strip() else {}
            except json.JSONDecodeError:
                return f"Error: {self.name} got non-JSON arguments: {args!r}"
        try:
            result = self.func(**args)
        except TypeError as e:
            return f"Error: bad arguments for {self.name}: {e}"
        except Exception as e:  # noqa: BLE001 — surface any tool failure to the model
            return f"Error: {self.name} failed: {e}"
        return result if isinstance(result, str) else str(result)


def tool(func: Callable[..., Any]) -> Tool:
    """Decorator: build a Tool from a typed, documented function.

    The model needs a JSON-schema description of each argument to call a tool.
    We derive that automatically by reading the function's type hints (for the
    argument types) and signature (to tell required args from optional ones).
    """
    try:
        hints = get_type_hints(func)        # {"query": str, "db_path": str, ...}
    except Exception:
        hints = {}
    sig = inspect.signature(func)

    properties: dict[str, dict] = {}
    required: list[str] = []
    for pname, param in sig.parameters.items():
        if pname == "self":
            continue
        # Each parameter becomes one JSON-schema property: {"query": {"type": "string"}}
        properties[pname] = _json_type(hints.get(pname, str))
        # A parameter with no default is required; one with a default is optional.
        if param.default is inspect.Parameter.empty:
            required.append(pname)

    parameters: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        parameters["required"] = required

    # The docstring becomes the tool description the model reads to decide when
    # to call it — so every @tool function must have a clear one.
    description = inspect.getdoc(func) or func.__name__
    return Tool(
        name=func.__name__,
        description=description,
        parameters=parameters,
        func=func,
    )

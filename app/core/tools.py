"""Tool registry. A tool is a plain function registered with @tool; workflows call tools by name
through RunContext.call(), which records every call (args, outcome, retries) in the trace."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .errors import UnknownTool


@dataclass
class ToolSpec:
    name: str
    description: str
    fn: Callable
    retries: int = 0          # extra attempts on TransientToolError
    needs_ctx: bool = False   # inject the RunContext as first arg (e.g. LLM / report writer)


_TOOLS: dict[str, ToolSpec] = {}


def tool(name: str, description: str, retries: int = 0, needs_ctx: bool = False):
    def deco(fn: Callable) -> Callable:
        _TOOLS[name] = ToolSpec(name, description, fn, retries, needs_ctx)
        return fn
    return deco


def get_tool(name: str) -> ToolSpec:
    try:
        return _TOOLS[name]
    except KeyError as exc:
        raise UnknownTool(f"Tool not registered: {name}") from exc


def list_tools() -> dict[str, ToolSpec]:
    return dict(_TOOLS)

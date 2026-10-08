"""Workflow plugin registry.

A workflow implementation is ONE small module in app/workflows/ that registers itself:

    @workflow("WF011", inputs=[InputSpec(...)])
    def run(ctx): ...

The Excel file stays the source of truth for names, triggers, steps and decision text;
the plugin only supplies the executable logic. Modules are auto-discovered, so adding a
workflow = 1 Excel row + 1 file. No router/engine/UI edits.
"""
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from typing import Callable

_SPECS: dict[str, "WorkflowSpec"] = {}


@dataclass
class InputSpec:
    name: str
    description: str = ""
    required: bool = False
    default: object = None
    kind: str = "text"            # text | file | number | list | json
    pattern: str | None = None    # regex used to pull the value out of a free-text request
    primary: bool = False         # a bare file path in the request is assigned to this input
    question: str | None = None   # what to ask the user if it is missing


@dataclass
class WorkflowSpec:
    workflow_id: str
    run: Callable
    inputs: list[InputSpec] = field(default_factory=list)
    any_of: list[list[str]] = field(default_factory=list)   # at least one of each group is required
    any_of_question: str | None = None


def workflow(workflow_id: str, inputs: list[InputSpec] | None = None,
             any_of: list[list[str]] | None = None, any_of_question: str | None = None):
    def deco(fn: Callable) -> Callable:
        _SPECS[workflow_id] = WorkflowSpec(workflow_id, fn, inputs or [], any_of or [], any_of_question)
        return fn
    return deco


def discover() -> None:
    """Import every module in app.workflows so their @workflow decorators run."""
    import app.workflows as pkg
    for mod in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module(f"{pkg.__name__}.{mod.name}")
    import app.tools as tools_pkg
    for mod in pkgutil.iter_modules(tools_pkg.__path__):
        importlib.import_module(f"{tools_pkg.__name__}.{mod.name}")


def get_spec(workflow_id: str) -> WorkflowSpec | None:
    return _SPECS.get(workflow_id)


def all_specs() -> dict[str, WorkflowSpec]:
    return dict(_SPECS)

"""Plain data models returned by the engine/agent (JSON-friendly)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ToolCall:
    tool: str
    args: dict[str, Any]
    status: str = "success"          # success | failed
    summary: str = ""
    duration_ms: float = 0.0
    attempts: int = 1
    error: str | None = None


@dataclass
class StepRecord:
    index: int
    name: str                         # label taken from the Excel "Steps" column
    status: str = "not_run"           # not_run | running | success | failed | blocked
    detail: str = ""
    duration_ms: float = 0.0
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass
class RunResult:
    workflow_id: str
    workflow_name: str
    status: str                       # success | needs_input | escalated | failed | not_implemented
    summary: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    steps: list[StepRecord] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    defaults_used: list[str] = field(default_factory=list)
    question: str | None = None
    missing: list[str] = field(default_factory=list)
    error: str | None = None
    artifacts: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    llm_mode: str = "offline"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Selection:
    workflow_id: str | None
    workflow_name: str | None
    confidence: float
    reason: str
    method: str                       # llm | lexical
    alternatives: list[dict] = field(default_factory=list)
    clarification: str | None = None  # set when the request is too ambiguous to route

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentResponse:
    request: str
    selection: Selection
    result: RunResult | None

    def to_dict(self) -> dict:
        return {"request": self.request, "selection": self.selection.to_dict(),
                "result": self.result.to_dict() if self.result else None}

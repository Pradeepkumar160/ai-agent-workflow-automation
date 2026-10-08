"""RunContext: what a workflow handler uses to run steps and call tools while being traced."""
from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pandas as pd

from app.models import StepRecord, ToolCall
from .errors import NeedsInput, TransientToolError
from .tools import get_tool


def _short(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return f"<table {value.shape[0]}x{value.shape[1]}>"
    if isinstance(value, pd.Series):
        return f"<series n={len(value)}>"
    if callable(value):
        return f"<callable {getattr(value, '__name__', 'fn')}>"
    if isinstance(value, (list, tuple, set)):
        return f"<{type(value).__name__} n={len(value)}>" if len(value) > 6 else list(value)
    if isinstance(value, dict):
        return f"<dict keys={list(value)[:6]}>" if len(str(value)) > 120 else value
    text = str(value)
    return text if len(text) <= 120 else text[:117] + "..."


def _result_summary(res: Any) -> str:
    if isinstance(res, pd.DataFrame):
        return f"table with {len(res)} rows, {len(res.columns)} columns"
    if isinstance(res, pd.Series):
        return f"series of {len(res)} values"
    if isinstance(res, dict):
        return "dict(" + ", ".join(list(res)[:6]) + ")"
    if isinstance(res, (list, tuple)):
        return f"{len(res)} items"
    return str(_short(res))


class RunContext:
    def __init__(self, workflow, inputs: dict, llm, output_dir: Path):
        self.workflow = workflow
        self.inputs = inputs
        self.llm = llm
        self.output_dir = Path(output_dir)
        self.steps = [StepRecord(i, name) for i, name in enumerate(workflow.steps)]
        self.artifacts: list[str] = []
        self._current: StepRecord | None = None
        self.loose_calls: list[ToolCall] = []

    # ---- steps -------------------------------------------------------------------------
    def _step_record(self, index: int) -> StepRecord:
        while index >= len(self.steps):  # Excel shorter than handler: keep going gracefully
            self.steps.append(StepRecord(len(self.steps), f"Step {len(self.steps) + 1}"))
        return self.steps[index]

    @contextmanager
    def step(self, index: int):
        """Run Excel step #index (0-based). Status/timing/tool calls are recorded automatically."""
        rec = self._step_record(index)
        rec.status, prev, t0 = "running", self._current, time.perf_counter()
        self._current = rec
        try:
            yield rec
            rec.status = "success"
        except NeedsInput:
            rec.status = "blocked"
            raise
        except Exception:
            rec.status = "failed"
            raise
        finally:
            rec.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            self._current = prev

    def note(self, text: str) -> None:
        if self._current is not None:
            self._current.detail = (self._current.detail + " | " if self._current.detail else "") + text

    # ---- tools -------------------------------------------------------------------------
    def call(self, tool_name: str, **kwargs):
        spec = get_tool(tool_name)
        record = ToolCall(tool=tool_name, args={k: _short(v) for k, v in kwargs.items()})
        (self._current.tool_calls if self._current else self.loose_calls).append(record)
        t0 = time.perf_counter()
        attempts = spec.retries + 1
        for attempt in range(1, attempts + 1):
            record.attempts = attempt
            try:
                res = spec.fn(self, **kwargs) if spec.needs_ctx else spec.fn(**kwargs)
                record.status, record.summary = "success", _result_summary(res)
                record.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
                return res
            except TransientToolError as exc:
                record.error = f"attempt {attempt} failed: {exc}"
                if attempt == attempts:
                    break
            except Exception as exc:
                record.status, record.error = "failed", f"{type(exc).__name__}: {exc}"
                record.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
                raise
        record.status = "failed"
        record.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        raise TransientToolError(record.error or "tool failed after retries")

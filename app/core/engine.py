"""Generic workflow engine: resolve inputs -> check required -> run plugin -> trace -> result.
Contains NO workflow-specific logic."""
from __future__ import annotations

import time
from pathlib import Path

from app.config import OUTPUT_DIR
from app.models import RunResult
from app.workflow.schema import WorkflowDefinition
from .context import RunContext
from .errors import NeedsInput, TransientToolError, WorkflowDataError
from .registry import WorkflowSpec, get_spec


def _blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (list, dict)) and not v)


class WorkflowEngine:
    def __init__(self, llm, output_dir: Path | None = None):
        self.llm = llm
        self.output_dir = Path(output_dir or OUTPUT_DIR)

    # ---- input resolution ----------------------------------------------------------------
    @staticmethod
    def resolve_inputs(spec: WorkflowSpec, provided: dict) -> tuple[dict, list[str]]:
        inputs = {k: v for k, v in (provided or {}).items() if not _blank(v)}
        defaults_used: list[str] = []
        for s in spec.inputs:
            if _blank(inputs.get(s.name)) and not _blank(s.default):
                inputs[s.name] = s.default
                defaults_used.append(s.name)
        return inputs, defaults_used

    @staticmethod
    def missing_inputs(spec: WorkflowSpec, inputs: dict) -> tuple[list[str], str | None]:
        missing = [s for s in spec.inputs if s.required and _blank(inputs.get(s.name))]
        questions = [s.question or f"Please provide: {s.description or s.name}." for s in missing]
        names = [s.name for s in missing]
        for group in spec.any_of:
            if all(_blank(inputs.get(n)) for n in group):
                names.extend(group)
                questions.append(spec.any_of_question or f"Please provide at least one of: {', '.join(group)}.")
        return names, (" ".join(questions) if questions else None)

    # ---- execution -----------------------------------------------------------------------
    def run(self, workflow: WorkflowDefinition, provided_inputs: dict | None = None) -> RunResult:
        t0 = time.perf_counter()
        base = dict(workflow_id=workflow.workflow_id, workflow_name=workflow.workflow_name,
                    llm_mode=self.llm.mode)
        spec = get_spec(workflow.workflow_id)
        if spec is None:
            return RunResult(**base, status="not_implemented",
                             error=f"{workflow.workflow_id} is defined in Excel but has no implementation "
                                   f"module in app/workflows/.",
                             summary="Workflow is defined but not implemented yet.")

        inputs, defaults_used = self.resolve_inputs(spec, provided_inputs or {})
        ctx = RunContext(workflow, inputs, self.llm, self.output_dir)
        result = RunResult(**base, status="running", steps=ctx.steps, inputs=inputs, defaults_used=defaults_used)

        missing, question = self.missing_inputs(spec, inputs)
        if missing:
            result.status, result.question, result.missing = "needs_input", question, missing
            result.summary = question or ""
            result.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            return result

        try:
            out = spec.run(ctx) or {}
            result.status = out.get("status", "success")
            result.summary = out.get("summary", "")
            result.data = out.get("data", {})
            result.question = out.get("question")
        except NeedsInput as exc:
            result.status, result.question, result.summary = "needs_input", exc.question, exc.question
            result.missing = exc.missing
        except (FileNotFoundError, WorkflowDataError, ValueError, KeyError) as exc:
            result.status = "failed"
            result.error = f"{type(exc).__name__}: {exc}"
            result.summary = f"Workflow could not complete: {exc}"
        except TransientToolError as exc:
            result.status, result.error = "failed", f"Tool unavailable after retries: {exc}"
            result.summary = "A required tool/API is temporarily unavailable. Please retry."
        except Exception as exc:  # last-resort guard so the agent never crashes
            result.status, result.error = "failed", f"Unexpected {type(exc).__name__}: {exc}"
            result.summary = "Unexpected error while running the workflow."
        result.artifacts = list(ctx.artifacts)
        result.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        return result

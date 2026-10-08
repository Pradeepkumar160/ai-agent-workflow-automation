"""Exception types the engine understands (each maps to a clear run status)."""
from __future__ import annotations


class NeedsInput(Exception):
    """A required input is missing/invalid -> ask the user (status=needs_input)."""

    def __init__(self, question: str, missing: list[str] | None = None):
        super().__init__(question)
        self.question = question
        self.missing = missing or []


class WorkflowDataError(Exception):
    """Data/config problem (bad file, missing columns...) -> status=failed with a clear message."""


class TransientToolError(Exception):
    """A tool/API failed in a retryable way (timeout, 503...)."""


class UnknownTool(KeyError):
    pass

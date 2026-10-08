"""WorkflowAgent: request -> select workflow -> extract inputs -> execute -> result."""
from __future__ import annotations

from pathlib import Path

from app.config import EXCEL_PATH, OUTPUT_DIR
from app.core import registry
from app.core.engine import WorkflowEngine
from app.llm import LLMClient, get_llm
from app.models import AgentResponse, RunResult
from app.workflow.registry import WorkflowCatalog
from .extract import extract_inputs
from .router import WorkflowRouter


class WorkflowAgent:
    def __init__(self, excel_path: str | Path | None = None, llm: LLMClient | None = None,
                 output_dir: str | Path | None = None):
        registry.discover()
        self.llm = llm or get_llm()
        self.catalog = WorkflowCatalog(excel_path or EXCEL_PATH)
        self.router = WorkflowRouter(self.catalog.all(), self.llm)
        self.engine = WorkflowEngine(self.llm, Path(output_dir or OUTPUT_DIR))

    def handle(self, request: str, inputs: dict | None = None, workflow_id: str | None = None) -> AgentResponse:
        """workflow_id forces a workflow (manual override); otherwise the router decides."""
        if workflow_id:
            wf = self.catalog.get(workflow_id)
            from app.models import Selection
            selection = Selection(wf.workflow_id, wf.workflow_name, 1.0, "Workflow chosen manually.", "manual")
        else:
            selection = self.router.select(request)
        if selection.workflow_id is None:
            return AgentResponse(request, selection, None)
        wf = self.catalog.get(selection.workflow_id)
        spec = registry.get_spec(wf.workflow_id)
        provided = extract_inputs(request, spec, self.llm) if spec else {}
        provided.update({k: v for k, v in (inputs or {}).items() if v not in (None, "")})  # explicit inputs win
        result: RunResult = self.engine.run(wf, provided)
        return AgentResponse(request, selection, result)

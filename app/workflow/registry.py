from pathlib import Path

from .loader import load_workflows_from_excel
from .schema import WorkflowDefinition


class WorkflowCatalog:
    """Workflow definitions loaded from the Excel source of truth."""

    def __init__(self, excel_path: str | Path):
        self.excel_path = Path(excel_path)
        self._workflows = load_workflows_from_excel(self.excel_path)

    def get(self, workflow_id: str) -> WorkflowDefinition:
        try:
            return self._workflows[workflow_id]
        except KeyError as exc:
            raise KeyError(f"Unknown workflow ID: {workflow_id}") from exc

    def all(self) -> list[WorkflowDefinition]:
        return list(self._workflows.values())

    def ids(self) -> list[str]:
        return list(self._workflows)

    def __contains__(self, workflow_id: str) -> bool:
        return workflow_id in self._workflows

    def __len__(self) -> int:
        return len(self._workflows)


WorkflowRegistry = WorkflowCatalog  # backwards-compatible alias

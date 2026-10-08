from pydantic import BaseModel, Field


class WorkflowDefinition(BaseModel):
    workflow_id: str
    workflow_name: str
    trigger: str
    inputs: str
    steps: list[str] = Field(default_factory=list)
    decision_logic: str
    tools_required: list[str] = Field(default_factory=list)
    expected_output: str

    @property
    def description(self) -> str:
        return f"{self.workflow_id} - {self.workflow_name}"

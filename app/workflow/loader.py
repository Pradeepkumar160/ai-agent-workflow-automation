from pathlib import Path
import pandas as pd

from .schema import WorkflowDefinition

REQUIRED_COLUMNS = [
    "Workflow_ID",
    "Workflow_Name",
    "Trigger",
    "Inputs",
    "Steps",
    "Decision_Logic",
    "Tools_Required",
    "Expected_Output",
]


def _split_arrow_steps(value: str) -> list[str]:
    return [part.strip() for part in str(value).split("→") if part.strip()]


def _split_semicolon(value: str) -> list[str]:
    return [part.strip() for part in str(value).split(";") if part.strip()]


def load_workflows_from_excel(path: str | Path) -> dict[str, WorkflowDefinition]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Workflow Excel file not found: {path}")

    frame = pd.read_excel(path, sheet_name="Workflows")
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required Excel columns: {missing}")

    workflows: dict[str, WorkflowDefinition] = {}
    for row in frame.to_dict(orient="records"):
        workflow = WorkflowDefinition(
            workflow_id=str(row["Workflow_ID"]).strip(),
            workflow_name=str(row["Workflow_Name"]).strip(),
            trigger=str(row["Trigger"]).strip(),
            inputs=str(row["Inputs"]).strip(),
            steps=_split_arrow_steps(row["Steps"]),
            decision_logic=str(row["Decision_Logic"]).strip(),
            tools_required=_split_semicolon(row["Tools_Required"]),
            expected_output=str(row["Expected_Output"]).strip(),
        )
        if workflow.workflow_id in workflows:
            raise ValueError(f"Duplicate workflow ID: {workflow.workflow_id}")
        workflows[workflow.workflow_id] = workflow

    if not workflows:
        raise ValueError("No workflows were found in the Excel file")

    return workflows


def load_test_questions(path: str | Path) -> pd.DataFrame:
    frame = pd.read_excel(path, sheet_name="Test_Questions")
    required = ["Workflow_ID", "Test_Request", "What_To_Check"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing test-question columns: {missing}")
    return frame

"""Central configuration: paths + environment."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

EXCEL_PATH = Path(os.getenv("WORKFLOW_EXCEL", ROOT / "data" / "AI_Agent_Workflow_Assessment.xlsx"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", ROOT / "outputs"))
MOCK_DIR = ROOT / "data" / "mock"


def resolve_path(value: str | os.PathLike) -> Path:
    """Resolve a user/default path: as given, else relative to the project root."""
    p = Path(str(value).strip().strip("'\""))
    if p.is_absolute() or p.exists():
        return p
    return ROOT / p


def mock(name: str) -> str:
    """Project-relative path of a bundled sample data file (used as workflow defaults)."""
    return f"data/mock/{name}"

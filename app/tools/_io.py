from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from app.config import resolve_path
from app.core.errors import WorkflowDataError


def snake(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def read_table(path, sheet=0) -> pd.DataFrame:
    p = resolve_path(path)
    if not p.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    suffix = p.suffix.lower()
    try:
        if suffix in (".csv", ".txt"):
            for enc in ("utf-8-sig", "latin-1"):
                try:
                    return pd.read_csv(p, dtype=str, encoding=enc, keep_default_na=False, na_values=[""])
                except UnicodeDecodeError:
                    continue
        if suffix == ".tsv":
            return pd.read_csv(p, sep="\t", dtype=str, keep_default_na=False, na_values=[""])
        if suffix in (".xlsx", ".xlsm", ".xls"):
            return pd.read_excel(p, sheet_name=sheet, dtype=str)
    except pd.errors.EmptyDataError as exc:
        raise WorkflowDataError(f"File is empty: {p.name}") from exc
    raise WorkflowDataError(f"Unsupported file type '{suffix}' for {p.name} (use CSV or XLSX)")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [snake(c) for c in out.columns]
    return out


def clean_cell(v):
    return v.strip() if isinstance(v, str) else v

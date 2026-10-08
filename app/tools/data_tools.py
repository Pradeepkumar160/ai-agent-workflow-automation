from __future__ import annotations

import pandas as pd

from app.core.errors import WorkflowDataError
from app.core.tools import tool
from ._io import normalize_columns, read_table, snake


@tool("csv_reader", "Read a CSV (or XLSX) file into a table; optionally normalise column names to snake_case")
def csv_reader(path: str, normalize: bool = True) -> pd.DataFrame:
    df = read_table(path)
    return normalize_columns(df) if normalize else df


@tool("excel_parser", "Parse an Excel workbook sheet (or CSV) into a table")
def excel_parser(path: str, sheet=0, normalize: bool = False) -> pd.DataFrame:
    df = read_table(path, sheet=sheet)
    return normalize_columns(df) if normalize else df


@tool("data_validation", "Check required columns exist and flag rows with empty required fields")
def data_validation(df: pd.DataFrame, required_columns: list[str], non_empty: list[str] | None = None) -> dict:
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        raise WorkflowDataError(f"Missing required columns: {missing}. Found: {list(df.columns)}")
    non_empty = non_empty or []
    reasons = pd.Series([""] * len(df), index=df.index, dtype=object)
    for col in non_empty:
        empty = df[col].isna() | (df[col].astype(str).str.strip() == "")
        reasons = reasons.where(~empty, reasons.map(lambda r, c=col: (r + "; " if r else "") + f"missing {c}"))
    return {"valid_mask": reasons == "", "reasons": reasons}


@tool("product_data_reader", "Read the product master data, optionally filtered by names or collection")
def product_data_reader(path: str, names: list[str] | None = None, collection: str | None = None) -> pd.DataFrame:
    df = read_table(path)
    df = df.rename(columns={c: snake(c) for c in df.columns})
    if collection and "collection" in df.columns:
        df = df[df["collection"].fillna("").str.lower() == collection.lower()]
    if names and "product_name" in df.columns:
        wanted = {n.lower().strip() for n in names}
        df = df[df["product_name"].fillna("").str.lower().isin(wanted)]
    return df.reset_index(drop=True)

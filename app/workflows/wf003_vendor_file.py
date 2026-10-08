"""WF003 Vendor File Processing."""
import pandas as pd

from app.config import mock
from app.core.errors import WorkflowDataError
from app.core.registry import InputSpec, workflow
from app.tools._io import clean_cell

ALIASES = {
    "sku": ["sku", "item_code", "vendor_sku", "part_number", "product_code", "item_no", "code", "item_number"],
    "product_name": ["product_name", "name", "title", "item_name", "product", "item_description"],
    "category": ["category", "cat", "product_category", "type"],
    "material": ["material", "mat"],
    "color": ["color", "colour"],
    "stock": ["stock", "qty", "quantity", "inventory", "on_hand"],
}


@workflow("WF003", inputs=[
    InputSpec("vendor_path", "Vendor CSV/XLSX file", default=mock("vendor_products.csv"), kind="file", primary=True)])
def run(ctx):
    path = str(ctx.inputs["vendor_path"])
    with ctx.step(0):  # Read file
        tool_name = "excel_parser" if path.lower().endswith((".xlsx", ".xls", ".xlsm")) else "csv_reader"
        raw = ctx.call(tool_name, path=path, normalize=True)
        ctx.note(f"{len(raw)} rows, columns: {list(raw.columns)}")

    with ctx.step(1):  # Detect columns
        mapping = {}
        for canonical, names in ALIASES.items():
            found = next((c for c in raw.columns if c in names), None)
            if found:
                mapping[found] = canonical
        ctx.note("detected: " + ", ".join(f"{k}->{v}" for k, v in mapping.items()))

    with ctx.step(2):  # Normalize column names
        df = raw.rename(columns=mapping)
        first = [c for c in ALIASES if c in df.columns]
        df = df[first + [c for c in df.columns if c not in first]]
        df = df.apply(lambda col: col.map(clean_cell))
        df = df.replace({"": None})

    with ctx.step(3):  # Validate required fields
        missing_cols = [c for c in ("sku", "product_name") if c not in df.columns]
        if missing_cols:
            raise WorkflowDataError(f"Cannot find required column(s) {missing_cols}. Columns present: {list(raw.columns)}")
        check = ctx.call("data_validation", df=df, required_columns=["sku", "product_name"],
                         non_empty=["sku", "product_name"])

    with ctx.step(4):  # Identify invalid rows   (decision: missing SKU or product name)
        valid_mask = check["valid_mask"]
        invalid = df[~valid_mask].copy()
        invalid.insert(0, "source_row", invalid.index + 2)       # +2 = spreadsheet row (header is row 1)
        invalid["reason"] = check["reasons"][~valid_mask]
        valid = df[valid_mask]

    with ctx.step(5):  # Produce cleaned dataset
        clean = valid.drop_duplicates().reset_index(drop=True)
        exact_dupes = len(valid) - len(clean)
        conflicting = clean[clean.duplicated("sku", keep=False)]["sku"].unique().tolist()
        clean_path = ctx.call("reporting", name="wf003_cleaned_vendor_file", content=clean.to_dict("records"))
        bad_path = ctx.call("reporting", name="wf003_invalid_rows", content=invalid.to_dict("records"))
    inv_rows = invalid.astype(object).where(invalid.notna(), None).to_dict("records")
    summary = (f"Processed {len(df)} rows: {len(valid)} valid, {len(invalid)} invalid. "
               f"Cleaned dataset has {len(clean)} rows ({exact_dupes} exact duplicate row(s) removed)."
               + (f" Warning - SKU(s) repeated with different data: {', '.join(conflicting)}." if conflicting else "")
               + "\nInvalid rows:\n" + "\n".join(f"- row {r['source_row']}: {r['reason']}" for r in inv_rows)
               + f"\nCleaned file: {clean_path}; invalid-row report: {bad_path}")
    return {"summary": summary, "data": {"rows_read": len(df), "valid_rows": len(valid), "invalid_rows": len(invalid),
            "cleaned_rows": len(clean), "exact_duplicates_removed": exact_dupes, "conflicting_duplicate_skus": conflicting,
            "column_mapping": mapping, "invalid_row_report": inv_rows, "cleaned_preview": clean.head(5).to_dict("records")}}

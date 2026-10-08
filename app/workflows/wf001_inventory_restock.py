"""WF001 Inventory Restock Check."""
import pandas as pd

from app.config import mock
from app.core.registry import InputSpec, workflow


@workflow("WF001", inputs=[
    InputSpec("inventory_path", "Inventory CSV", default=mock("inventory.csv"), kind="file", primary=True),
    InputSpec("minimum_stock", "Override minimum-stock threshold for all products", kind="number",
              pattern=r"(?:threshold|minimum|below|under)\D{0,12}(\d+)"),
    InputSpec("reorder_multiplier", "Restock up to N x the minimum stock", default=2, kind="number"),
])
def run(ctx):
    with ctx.step(0):  # Load inventory
        df = ctx.call("csv_reader", path=ctx.inputs["inventory_path"])
        ctx.call("data_validation", df=df, required_columns=["sku", "product_name", "current_stock", "minimum_stock"])
        ctx.note(f"{len(df)} inventory rows loaded")

    with ctx.step(1):  # Compare current stock with minimum threshold
        df["current_stock"] = pd.to_numeric(df["current_stock"], errors="coerce")
        df["minimum_stock"] = pd.to_numeric(df["minimum_stock"], errors="coerce")
        if ctx.inputs.get("minimum_stock") is not None:
            df["minimum_stock"] = float(ctx.inputs["minimum_stock"])
            ctx.note(f"threshold overridden to {ctx.inputs['minimum_stock']}")
        bad = df[df["current_stock"].isna() | df["minimum_stock"].isna()]
        good = df.drop(bad.index)
        ctx.note(f"{len(bad)} rows skipped (non-numeric stock)")

    with ctx.step(2):  # Identify low-stock products   (decision: current_stock < minimum_stock)
        low = good[good["current_stock"] < good["minimum_stock"]].copy()

    with ctx.step(3):  # Calculate reorder quantity
        mult = float(ctx.inputs["reorder_multiplier"])
        low["reorder_quantity"] = ctx.call("calculator", op="reorder_quantity", current=low["current_stock"],
                                           minimum=low["minimum_stock"], multiplier=mult)

    with ctx.step(4):  # Generate restock list
        low = low.assign(_gap=low["current_stock"] / low["minimum_stock"]).sort_values("_gap")
        items = [{"sku": r.sku, "product_name": r.product_name, "current_stock": int(r.current_stock),
                  "minimum_stock": int(r.minimum_stock), "reorder_quantity": int(r.reorder_quantity)}
                 for r in low.itertuples()]
        skipped = [{"sku": r.sku, "reason": f"non-numeric stock values ({r.current_stock}/{r.minimum_stock})"}
                   for r in bad.itertuples()]
    if items:
        lines = [f"- {i['sku']} {i['product_name']}: stock {i['current_stock']} < min {i['minimum_stock']} "
                 f"-> reorder {i['reorder_quantity']}" for i in items]
        summary = f"{len(items)} of {len(good)} products need restocking:\n" + "\n".join(lines)
    else:
        summary = f"No products need restocking ({len(good)} checked)."
    if skipped:
        summary += f"\n{len(skipped)} row(s) skipped due to invalid stock data: " + ", ".join(s['sku'] for s in skipped)
    return {"summary": summary, "data": {"rule": "restock if current_stock < minimum_stock",
            "reorder_rule": f"restock up to {mult:g} x minimum stock", "products_checked": len(good),
            "restock_count": len(items), "items": items, "skipped_rows": skipped}}

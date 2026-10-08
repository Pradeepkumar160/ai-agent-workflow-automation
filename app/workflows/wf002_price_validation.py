"""WF002 Product Price Validation."""
import pandas as pd

from app.config import mock
from app.core.registry import InputSpec, workflow
from app.tools.text_tools import normalize_sku


@workflow("WF002", inputs=[
    InputSpec("product_path", "Internal product CSV", default=mock("products.csv"), kind="file"),
    InputSpec("vendor_path", "Vendor price list CSV", default=mock("vendor_prices.csv"), kind="file", primary=True),
    InputSpec("threshold_percent", "Flag when difference exceeds this %", default=10, kind="number",
              pattern=r"(\d+(?:\.\d+)?)\s*(?:%|percent)"),
])
def run(ctx):
    threshold = float(ctx.inputs["threshold_percent"])
    with ctx.step(0):  # Load product prices
        internal = ctx.call("csv_reader", path=ctx.inputs["product_path"])
        vendor = ctx.call("csv_reader", path=ctx.inputs["vendor_path"])
        ctx.call("data_validation", df=internal, required_columns=["sku", "internal_price"])
        ctx.call("data_validation", df=vendor, required_columns=["sku", "vendor_price"])
        ctx.note(f"{len(internal)} internal rows, {len(vendor)} vendor rows")

    with ctx.step(1):  # Match products by SKU
        internal["_key"] = internal["sku"].map(normalize_sku)
        vendor["_key"] = vendor["sku"].map(normalize_sku)
        slim = vendor[["_key", "sku", "vendor_price"]].rename(columns={"sku": "vendor_sku"})
        merged = internal.merge(slim, on="_key", how="outer", indicator=True)
        only_internal = merged[merged["_merge"] == "left_only"]
        only_vendor = merged[merged["_merge"] == "right_only"]
        both = merged[merged["_merge"] == "both"].copy()
        ctx.note(f"{len(both)} matched, {len(only_internal)} internal-only, {len(only_vendor)} vendor-only")

    with ctx.step(2):  # Compare internal and vendor prices
        both["internal_price"] = pd.to_numeric(both["internal_price"], errors="coerce")
        both["vendor_price"] = pd.to_numeric(both["vendor_price"], errors="coerce")
        invalid = both[both["internal_price"].isna() | both["vendor_price"].isna() | (both["internal_price"] <= 0)]
        both = both.drop(invalid.index)

    with ctx.step(3):  # Calculate percentage difference  ((vendor - internal) / internal)
        both["diff_pct"] = ctx.call("calculator", op="percentage_difference",
                                    base=both["internal_price"], other=both["vendor_price"])

    with ctx.step(4):  # Flag exceptions   (decision: |difference| > threshold)
        both["flagged"] = both["diff_pct"].abs() > threshold
        rows = [{"sku": r.sku, "product_name": getattr(r, "product_name", None), "internal_price": r.internal_price,
                 "vendor_price": r.vendor_price, "difference_percent": round(float(r.diff_pct), 2),
                 "exception": bool(r.flagged)} for r in both.itertuples()]
    exceptions = [r for r in rows if r["exception"]]
    unmatched = {"internal_only": only_internal["sku"].tolist(),
                 "vendor_only": [str(x).strip() for x in only_vendor["vendor_sku"].tolist()],
                 "invalid_prices": invalid["sku"].tolist()}
    lines = [f"- {e['sku']} {e['product_name']}: internal {e['internal_price']:g} vs vendor {e['vendor_price']:g} "
             f"({e['difference_percent']:+.1f}%)" for e in exceptions]
    summary = (f"{len(rows)} products matched; {len(exceptions)} exceed the {threshold:g}% threshold:\n"
               + "\n".join(lines)) if exceptions else f"{len(rows)} products matched; none exceed {threshold:g}%."
    notes = [f"{k.replace('_', ' ')}: {', '.join(map(str, v))}" for k, v in unmatched.items() if v]
    if notes:
        summary += "\nNot validated -> " + "; ".join(notes)
    return {"summary": summary, "data": {"rule": f"flag when |vendor-internal|/internal > {threshold:g}%",
            "matched": len(rows), "exception_count": len(exceptions), "results": rows, "unmatched": unmatched}}

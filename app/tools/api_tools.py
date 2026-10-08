"""Simulated external systems (order database + shipment/carrier API) backed by mock CSV files."""
from __future__ import annotations

import pandas as pd

from app.core.errors import TransientToolError
from app.core.tools import tool
from ._io import normalize_columns, read_table

_FLAKY = {"fail_next": 0}   # test hook: make the simulated API fail N times to exercise retries


@tool("order_api", "Order database lookup by order ID or customer email (simulated API)", retries=2)
def order_api(path: str, order_id: str | None = None, customer_email: str | None = None) -> list[dict]:
    if _FLAKY["fail_next"] > 0:
        _FLAKY["fail_next"] -= 1
        raise TransientToolError("order service timeout (simulated)")
    df = normalize_columns(read_table(path))
    if order_id:
        rows = df[df["order_id"].fillna("").str.upper() == order_id.strip().upper()]
    else:
        rows = df[df["customer_email"].fillna("").str.lower() == (customer_email or "").strip().lower()]
    return rows.to_dict("records")


@tool("shipment_lookup", "Shipment/carrier tracking lookup by order ID (simulated API)", retries=2)
def shipment_lookup(path: str, order_id: str) -> dict | None:
    df = normalize_columns(read_table(path))
    rows = df[df["order_id"].fillna("").str.upper() == order_id.strip().upper()]
    return None if rows.empty else {k: (None if pd.isna(v) else v) for k, v in rows.iloc[0].to_dict().items()}

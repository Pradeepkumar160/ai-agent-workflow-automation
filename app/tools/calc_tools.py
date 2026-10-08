from __future__ import annotations

import math

import numpy as np
import pandas as pd

from app.core.errors import WorkflowDataError
from app.core.tools import tool


def _s(x):
    return pd.to_numeric(x, errors="coerce") if isinstance(x, (pd.Series, list)) else float(x)


@tool("calculator", "Arithmetic helpers (vectorised): reorder_quantity, percentage_difference, rate, mean")
def calculator(op: str, **kw):
    if op == "reorder_quantity":
        target = _s(kw["minimum"]) * float(kw.get("multiplier", 2))
        gap = target - _s(kw["current"])
        gap = gap.clip(lower=0) if isinstance(gap, pd.Series) else max(gap, 0)
        return np.ceil(gap) if isinstance(gap, pd.Series) else math.ceil(gap)
    if op == "percentage_difference":  # signed %, relative to `base`
        base, other = _s(kw["base"]), _s(kw["other"])
        if isinstance(base, pd.Series):
            return (other - base) / base.where(base != 0) * 100
        if base == 0:
            raise WorkflowDataError("Base value is zero; cannot compute percentage difference")
        return (other - base) / base * 100
    if op == "rate":
        total = kw["total"]
        return 0.0 if not total else kw["count"] / total * 100
    if op == "mean":
        vals = _s(kw["values"])
        return float(vals.mean()) if isinstance(vals, pd.Series) else float(np.mean(vals))
    raise WorkflowDataError(f"Unknown calculator op: {op}")

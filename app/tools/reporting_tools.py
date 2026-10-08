from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.core.tools import tool


@tool("reporting", "Write a result file (csv/json/md) into the outputs folder and return its path", needs_ctx=True)
def reporting(ctx, name: str, content, fmt: str = "csv") -> str:
    out = Path(ctx.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.{fmt}"
    if fmt == "csv":
        pd.DataFrame(content).to_csv(path, index=False)
    elif fmt == "json":
        path.write_text(json.dumps(content, indent=2, default=str), encoding="utf-8")
    else:
        path.write_text(str(content), encoding="utf-8")
    try:
        shown = str(path.relative_to(Path.cwd()))
    except ValueError:
        shown = str(path)
    ctx.artifacts.append(shown)
    return shown

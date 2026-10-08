from __future__ import annotations

from app.core.tools import tool


@tool("ranking_logic", "Rank candidate dicts by a numeric key (descending), stable tie-break by name")
def ranking_logic(candidates: list[dict], key: str = "score", tie_break: str = "name") -> list[dict]:
    return sorted(candidates, key=lambda c: (-float(c[key]), str(c.get(tie_break, ""))))

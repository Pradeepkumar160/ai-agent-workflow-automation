from __future__ import annotations

import re

from rapidfuzz import fuzz

from app.core.tools import tool


def normalize_text(s) -> str:
    s = re.sub(r"[^a-z0-9]+", " ", str(s).lower())
    return " ".join(s.split())


def normalize_sku(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


@tool("text_similarity", "Fuzzy similarity (0-1) between two strings, order-insensitive")
def text_similarity(a: str, b: str) -> float:
    return fuzz.token_sort_ratio(normalize_text(a), normalize_text(b)) / 100.0


@tool("pairwise_similarity", "All pairs of strings whose fuzzy similarity (0-1) is >= min_score")
def pairwise_similarity(names: list[str], min_score: float = 0.5) -> list[tuple[int, int, float]]:
    from rapidfuzz import process
    norm = [normalize_text(n) for n in names]
    matrix = process.cdist(norm, norm, scorer=fuzz.token_sort_ratio, score_cutoff=int(min_score * 100))
    out = []
    for i in range(len(norm)):
        for j in range(i + 1, len(norm)):
            if matrix[i][j] >= min_score * 100:
                out.append((i, j, float(matrix[i][j]) / 100))
    return out


def _cut(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-|")
    return cut or text[:limit]


@tool("text_validation", "Validate/trim generated text fields (non-empty, max length, banned terms)")
def text_validation(fields: dict, limits: dict | None = None, banned_terms: list[str] | None = None) -> dict:
    limits, issues, fixed = limits or {}, [], {}
    for key, value in fields.items():
        text = " ".join(str(value or "").split())
        if not text:
            issues.append(f"{key} is empty")
        for term in banned_terms or []:
            if term.lower() in text.lower():
                issues.append(f"{key} contains banned term '{term}'")
        if key in limits and len(text) > limits[key]:
            issues.append(f"{key} trimmed from {len(text)} to <= {limits[key]} chars")
            text = _cut(text, limits[key])
        fixed[key] = text
    return {"ok": not any("empty" in i or "banned" in i for i in issues), "issues": issues, "fields": fixed}

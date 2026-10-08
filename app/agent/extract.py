"""Pull workflow inputs out of a free-text request using the workflow's own InputSpec patterns
(+ optional LLM extraction). Generic: nothing here knows about a specific workflow."""
from __future__ import annotations

import json
import re

from app.core.registry import WorkflowSpec
from app.llm import LLMClient

FILE_RE = re.compile(r"[\w./\\:-]+\.(?:csv|xlsx|xls|tsv)\b", re.I)


def _norm(k: str) -> str:
    return re.sub(r"[^a-z0-9]", "", k.lower())


def extract_inputs(request: str, spec: WorkflowSpec, llm: LLMClient | None = None) -> dict:
    found: dict = {}
    by_norm = {_norm(s.name): s for s in spec.inputs}
    # 1) explicit "name: value" / "name=value" pairs
    for m in re.finditer(r"\b([A-Za-z_ ]{3,30}?)\s*[:=]\s*([^;\n]+)", request):
        s = by_norm.get(_norm(m.group(1)))
        if s and s.name not in found:
            found[s.name] = m.group(2).strip()
    # 2) per-input regex patterns
    for s in spec.inputs:
        if s.name in found or not s.pattern:
            continue
        m = re.search(s.pattern, request, flags=re.I)
        if m:
            val = next((g for g in m.groups() if g), None) or m.group(0)
            found[s.name] = val.strip()
    # 3) a bare file path goes to the primary file input
    primary = next((s for s in spec.inputs if s.primary), None)
    if primary and primary.name not in found:
        path = FILE_RE.search(request)
        if path:
            found[primary.name] = path.group(0)
    # 4) optional LLM extraction fills what regex missed
    if llm is not None and llm.available and spec.inputs:
        try:
            fields = {s.name: s.description or s.name for s in spec.inputs if s.kind != "file"}
            out = llm.chat_json("Extract input values from the user's request. Only include values that are explicitly "
                                "stated; never guess. Reply JSON with a subset of these keys: " + json.dumps(fields),
                                request)
            for k, v in out.items():
                if k in fields and v not in (None, "", []) and k not in found:
                    found[k] = v
        except Exception:
            pass
    for s in spec.inputs:                      # type coercion
        v = found.get(s.name)
        if v is None:
            continue
        if s.kind == "number":
            try:
                found[s.name] = float(v) if "." in str(v) else int(float(v))
            except ValueError:
                found.pop(s.name)
        elif s.kind == "list" and isinstance(v, str):
            found[s.name] = [x.strip() for x in re.split(r"[;,]", v) if x.strip()]
    return found

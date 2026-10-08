"""Workflow selection.

1. LLM routing (when an API key is set): the model sees the Excel-defined workflow catalog and returns
   {workflow_id, confidence, reason}. The answer is validated against the catalog.
2. Lexical routing (always available / fallback): weighted TF-IDF over every Excel column with light
   stemming. No workflow IDs or workflow-specific rules appear anywhere in this file.
If the best match is weak or ambiguous the router asks the user to clarify instead of guessing.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from app.llm import LLMClient
from app.models import Selection
from app.workflow.schema import WorkflowDefinition

STOP = set("a an and are as at be by can could do does for from give how i if in is it me my of on or our please show that "
           "the their them these this those to us was we what when where which who will with would you your tell need want "
           "find get check list run use using new all any most often now today current".split())
SUFFIXES = ["ations", "ation", "ings", "ing", "ures", "ure", "ions", "ion", "ers", "er", "ed", "es", "ly", "s"]
FIELD_WEIGHTS = {"workflow_name": 3.0, "trigger": 3.0, "expected_output": 1.0, "inputs": 1.0, "steps": 1.0,
                 "decision_logic": 1.0, "tools_required": 0.5}
MIN_SCORE, MIN_SHARE = 0.15, 0.30


def stem(w: str) -> str:
    for suf in SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            w = w[: -len(suf)]
            break
    return w[:-1] if w.endswith("e") and len(w) > 4 else w


def tokens(text: str) -> list[str]:
    return [stem(w) for w in re.findall(r"[a-z0-9]+", str(text).lower()) if w not in STOP and len(w) > 1]


class WorkflowRouter:
    def __init__(self, workflows: list[WorkflowDefinition], llm: LLMClient | None = None):
        if not workflows:
            raise ValueError("WorkflowRouter requires at least one workflow")
        self.workflows = list(workflows)
        self.llm = llm
        self._docs = []
        for w in self.workflows:
            c: Counter = Counter()
            for field, weight in FIELD_WEIGHTS.items():
                value = getattr(w, field)
                text = " ".join(value) if isinstance(value, list) else value
                for t in tokens(text):
                    c[t] += weight
            self._docs.append(c)
        n = len(self._docs)
        df = Counter(t for d in self._docs for t in d)
        self._idf = {t: math.log((n + 1) / (c + 0.5)) + 1 for t, c in df.items()}

    # ---- lexical ---------------------------------------------------------------------------
    def rank(self, request: str) -> list[tuple[WorkflowDefinition, float]]:
        q = Counter(tokens(request))
        scored = []
        for w, doc in zip(self.workflows, self._docs):
            s = sum(self._idf.get(t, 0) * math.log1p(doc[t]) * qc for t, qc in q.items() if t in doc)
            ident = 5.0 if w.workflow_id.lower() in request.lower() else 0.0
            scored.append((w, s / max(sum(self._idf.get(t, 0) * qc for t, qc in q.items()), 1e-9) + ident))
        return sorted(scored, key=lambda x: -x[1])

    def _lexical(self, request: str) -> Selection:
        ranked = self.rank(request)
        top, score = ranked[0]
        total = sum(s for _, s in ranked) or 1e-9
        share = score / total
        alts = [{"workflow_id": w.workflow_id, "workflow_name": w.workflow_name, "score": round(s, 3)}
                for w, s in ranked[1:4]]
        confidence = round(min(share * 1.6, 1.0), 3)  # share of total evidence, scaled to a readable 0-1
        if score < MIN_SCORE or share < MIN_SHARE:
            names = ", ".join(f"{w.workflow_id} {w.workflow_name}" for w, _ in ranked[:3])
            return Selection(None, None, confidence, "Request is too vague/ambiguous to pick a workflow.",
                             "lexical", alts, clarification=f"I'm not sure which workflow you mean. Closest matches: {names}. "
                                                              "Could you rephrase or name the workflow?")
        terms = sorted(set(tokens(request)) & set(self._docs[self.workflows.index(top)]))
        return Selection(top.workflow_id, top.workflow_name, confidence,
                         f"Request terms {terms} best match the workflow's name/trigger/steps in the Excel definition.",
                         "lexical", alts)

    # ---- LLM ---------------------------------------------------------------------------------
    def _llm(self, request: str) -> Selection:
        catalog = "\n".join(f"- {w.workflow_id}: {w.workflow_name} | trigger: {w.trigger} | inputs: {w.inputs} | "
                            f"output: {w.expected_output}" for w in self.workflows)
        system = ("You are a workflow router. Pick the single best workflow for the user's request from the catalog. "
                  "If none fits, use workflow_id null. Reply JSON: {\"workflow_id\": str|null, \"confidence\": 0-1, \"reason\": str}.")
        out = self.llm.chat_json(system, f"CATALOG:\n{catalog}\n\nUSER REQUEST: {request}")
        wid = out.get("workflow_id")
        by_id = {w.workflow_id: w for w in self.workflows}
        if wid is None:
            return Selection(None, None, float(out.get("confidence") or 0), out.get("reason", "No workflow fits"),
                             "llm", clarification="None of the available workflows match your request. "
                             "Available: " + ", ".join(w.workflow_name for w in self.workflows))
        if wid not in by_id:
            raise ValueError(f"LLM returned unknown workflow id {wid!r}")
        conf = max(0.0, min(float(out.get("confidence") or 0.0), 1.0))
        alts = [{"workflow_id": w.workflow_id, "workflow_name": w.workflow_name, "score": round(s, 3)}
                for w, s in self.rank(request)[:3] if w.workflow_id != wid]
        return Selection(wid, by_id[wid].workflow_name, conf, str(out.get("reason", "")), "llm", alts)

    def select(self, request: str) -> Selection:
        if not request or not request.strip():
            raise ValueError("User request cannot be empty")
        if self.llm is not None and self.llm.available:
            try:
                return self._llm(request)
            except Exception as exc:  # fall back to deterministic routing, but say so
                sel = self._lexical(request)
                sel.reason += f" (LLM routing failed -> lexical fallback: {exc})"
                return sel
        return self._lexical(request)

"""WF008 SEO Keyword Classification."""
import json

import pandas as pd

from app import llm_offline
from app.config import mock
from app.core.registry import InputSpec, workflow
from app.tools.text_tools import normalize_text

SYSTEM = ("You classify SEO keywords by search intent: informational, commercial, transactional or navigational. "
          "Return JSON {\"classifications\": {keyword: intent}}.")
PAGE_BY_INTENT = {"informational": "Blog / guide page", "navigational": "Home or account page",
                  "commercial": "Category page", "transactional": "Category / product page"}


@workflow("WF008", inputs=[
    InputSpec("keywords_path", "Keyword CSV (column: keyword)", default=mock("keywords.csv"), kind="file", primary=True),
    InputSpec("categories_path", "Category/page map", default=mock("categories.csv"), kind="file"),
])
def run(ctx):
    with ctx.step(0):  # Read keywords
        raw = ctx.call("csv_reader", path=ctx.inputs["keywords_path"])
        col = "keyword" if "keyword" in raw.columns else raw.columns[0]
        ctx.call("data_validation", df=raw, required_columns=[col], non_empty=[col])
        cats = ctx.call("csv_reader", path=ctx.inputs["categories_path"])
        ctx.note(f"{len(raw)} keywords read from column '{col}'")

    with ctx.step(1):  # Remove duplicates
        raw = raw[raw[col].notna() & (raw[col].str.strip() != "")]
        raw = raw.assign(_n=raw[col].map(normalize_text))
        deduped = raw.drop_duplicates("_n")[[col]].rename(columns={col: "keyword"}).reset_index(drop=True)
        removed = len(raw) - len(deduped)
        ctx.note(f"{removed} duplicate keyword(s) removed")
        keywords = deduped["keyword"].str.strip().tolist()

    with ctx.step(2):  # Classify search intent
        gen = ctx.call("llm", task="keyword_intent", facts={"keywords": keywords}, system=SYSTEM,
                       prompt="Classify each keyword:\n" + json.dumps(keywords))
        cls, fixed = gen["content"]["classifications"], 0
        intents = []
        for k in keywords:
            v = str(cls.get(k, "")).lower()
            if v not in llm_offline.INTENTS:   # validate model output; repair invalid/missing with the classifier
                v, fixed = llm_offline.classify_intent(k), fixed + 1
            intents.append(v)
        if fixed:
            ctx.note(f"{fixed} invalid/missing LLM label(s) repaired by rule-based classifier")

    with ctx.step(3):  # Map keywords to categories
        cat_rows = cats.to_dict("records")

        def map_cat(k):
            text = normalize_text(k)
            best, hits = None, 0
            for c in cat_rows:
                n = sum(1 for t in str(c["terms"]).split(";") if t.strip() and t.strip().lower() in text)
                if n > hits:
                    best, hits = c, n
            return best

        mapped = [map_cat(k) for k in keywords]

    with ctx.step(4):  # Identify high-priority keywords
        def priority(intent, cat):
            if intent in ("transactional", "commercial") and cat:
                return "high"
            if intent == "navigational":
                return "low"
            if intent == "informational" and not cat:
                return "low"
            return "medium"
        rows = []
        for k, i, c in zip(keywords, intents, mapped):
            page = (f"{PAGE_BY_INTENT[i]} -> {c['target_page']}" if c and i != "navigational"
                    else PAGE_BY_INTENT[i] if i == "navigational" else "Unmapped - needs manual review")
            rows.append({"keyword": k, "intent": i, "category": c["category"] if c else "Unmapped",
                         "priority": priority(i, c), "recommended_target_page": page})
        order = {"high": 0, "medium": 1, "low": 2}
        rows.sort(key=lambda r: (order[r["priority"]], r["keyword"]))

    with ctx.step(5):  # Export results
        path = ctx.call("reporting", name="wf008_keyword_report", content=rows)
    counts = pd.Series([r["intent"] for r in rows]).value_counts().to_dict()
    high = [r for r in rows if r["priority"] == "high"]
    summary = (f"{len(rows)} unique keywords classified ({removed} duplicates removed). Intent mix: {counts}. "
               f"{len(high)} high priority:\n" + "\n".join(f"- {r['keyword']} [{r['intent']}] -> {r['recommended_target_page']}" for r in high)
               + f"\nFull report: {path}")
    return {"summary": summary, "data": {"unique_keywords": len(rows), "duplicates_removed": removed,
            "intent_counts": counts, "classified_by": gen["source"], "keywords": rows}}

"""Deterministic offline fallbacks for LLM tasks. They only use facts they are given (never invent)."""
from __future__ import annotations

import re

INTENTS = ("informational", "commercial", "transactional", "navigational")
OBJECTIVES = ("launch", "awareness", "sales", "retention", "clearance")


def _join(*parts) -> str:
    return " ".join(str(p).strip() for p in parts if p not in (None, "", []))


def product_content(facts: dict) -> dict:
    name = facts["product_name"]
    category, color, material = facts.get("category"), facts.get("color"), facts.get("material")
    audience, attrs = facts.get("target_audience"), facts.get("attributes") or {}
    clauses = []
    if color:
        clauses.append(f"comes in {str(color).lower()}")
    if material:
        clauses.append(f"is made of {str(material).lower()}")
    if audience:
        clauses.append(f"is designed for {audience}")
    first = f"The {name}" + (f" ({category})" if category else "")
    if clauses:
        first += " " + (", ".join(clauses[:-1]) + (", and " if len(clauses) > 1 else "") + clauses[-1])
    first += "."
    extra = ""
    if attrs:
        extra = " Key details: " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in attrs.items()) + "."
    traits = ", ".join(str(x) for x in (color, material, category) if x)
    short = (f"{name} - {traits}" if traits else name)[:110]
    seo = f"{name} | {traits}" if traits else name
    meta = f"Shop the {name}" + (f" ({traits})" if traits else "") + (f" for {audience}" if audience else "") + "."
    return {"product_description": (first + extra).strip(), "short_description": short,
            "seo_title": seo, "meta_description": meta}


def campaign_messaging(facts: dict) -> dict:
    goal = (facts.get("goal") or "").lower()
    objective = next((o for o, kws in {
        "launch": ("launch", "introduce", "new collection", "unveil", "announce"),
        "clearance": ("clear", "liquidate", "end of season"),
        "retention": ("retain", "loyal", "repeat", "re-engage"),
        "sales": ("sales", "sell", "revenue", "conversion", "convert", "drive"),
        "awareness": ("awareness", "reach", "visibility", "brand"),
    }.items() if any(k in goal for k in kws)), "awareness")
    products = facts.get("products") or []
    promo, audience = facts.get("promotion"), facts.get("target_audience")
    names = ", ".join(products[:3]) if products else "our products"
    headline = _join(f"Meet {names}." if objective == "launch" else f"Discover {names}.",
                     promo and f"{promo}.")
    return {"objective_type": objective,
            "key_messages": [m for m in [
                headline,
                f"Built for {audience}." if audience else None,
                f"Offer: {promo}." if promo else None,
                "Clear call-to-action: shop now."] if m]}


_TRANSACTIONAL = ("buy", "price", "cheap", "deal", "discount", "order", "purchase", "coupon", "sale", "shop")
_COMMERCIAL = ("best", "top", "review", "compare", "vs", "alternative", "versus")
_INFORMATIONAL = ("how", "what", "why", "guide", "tutorial", "tips", "ideas", "when", "which", "difference", "diy")
_NAVIGATIONAL = ("login", "log in", "sign in", "official", "website", ".com", "near me", "contact", "store locator",
                 "customer service", "track order")


def classify_intent(keyword: str) -> str:
    k = f" {keyword.lower()} "
    if any(t in k for t in _NAVIGATIONAL):
        return "navigational"
    words = set(re.findall(r"[a-z0-9]+", k))
    if words & set(_TRANSACTIONAL):
        return "transactional"
    if words & set(_COMMERCIAL):
        return "commercial"
    if words & set(_INFORMATIONAL):
        return "informational"
    return "commercial"  # bare product terms ("wireless mouse") are commercial-investigation by default


def keyword_intent(facts: dict) -> dict:
    return {"classifications": {k: classify_intent(k) for k in facts["keywords"]}}


def recommendations(facts: dict) -> dict:
    recs = []
    for w in facts.get("flagged", []):
        parts = []
        if w.get("failure_rate", 0) > facts.get("failure_threshold", 10):
            parts.append(f"failure rate {w['failure_rate']:.0f}% exceeds {facts.get('failure_threshold', 10):g}%")
        if w.get("avg_execution_time", 0) > facts.get("time_threshold", 0):
            parts.append(f"average run time {w['avg_execution_time']:.1f}s exceeds {facts.get('time_threshold'):g}s")
        recs.append(f"{w['workflow_id']}: " + "; ".join(parts) + ". Review its top error and slowest step first.")
    for err, n in list(facts.get("frequent_errors", {}).items())[:3]:
        recs.append(f"Add retries/validation for the recurring error '{err}' ({n} occurrences).")
    for st in facts.get("slow_steps", [])[:2]:
        recs.append(f"Optimise or cache step '{st['step']}' of {st['workflow_id']} (avg {st['avg_seconds']:.1f}s).")
    if not recs:
        recs.append("All workflows are within thresholds; keep monitoring.")
    return {"recommendations": recs}


TASKS = {"product_content": product_content, "campaign_messaging": campaign_messaging,
         "keyword_intent": keyword_intent, "recommendations": recommendations}
REQUIRED_KEYS = {"product_content": ["product_description", "short_description", "seo_title", "meta_description"],
                 "campaign_messaging": ["objective_type", "key_messages"],
                 "keyword_intent": ["classifications"], "recommendations": ["recommendations"]}

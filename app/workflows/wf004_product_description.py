"""WF004 Product Description Generator (LLM + text validation; never invents missing attributes)."""
import json

from app.config import MOCK_DIR
from app.core.errors import NeedsInput
from app.core.registry import InputSpec, workflow

REQUIRED = ["product_name", "category", "material", "color", "target_audience"]
SYSTEM = ("You write e-commerce copy. Use ONLY the facts provided. Never invent or assume attributes, specs, "
          "materials, benefits or claims that are not in the facts. If an attribute is not provided, do not mention it.")


# Marketing claims the LLM likes to add. If one appears and is not in the supplied facts, it is an invention.
UNSUPPORTED = ["durable", "durability", "lightweight", "waterproof", "water-resistant", "premium", "luxury", "sleek",
               "stylish", "ample", "spacious", "comfortable", "high-quality", "sturdy", "rugged", "eco-friendly",
               "sustainable", "ergonomic", "breathable", "perfect", "reliable", "organized", "organization"]


def _invented(content: dict, facts: dict) -> list[str]:
    supplied = json.dumps(facts).lower()
    text = " ".join(str(v) for v in content.values()).lower()
    return sorted(w for w in UNSUPPORTED if w in text and w not in supplied)


def _default_product():
    return json.loads((MOCK_DIR / "sample_product.json").read_text())


@workflow("WF004", inputs=[
    InputSpec("product_name", "Product name", pattern=r"(?:for|product)\s+(?:the\s+)?['\"]([^'\"]+)['\"]"),
    InputSpec("category", "Category"), InputSpec("material", "Material"), InputSpec("color", "Colour"),
    InputSpec("target_audience", "Target audience"), InputSpec("attributes", "Other attributes", kind="json"),
])
def run(ctx):
    inp = dict(ctx.inputs)
    used_sample = False
    with ctx.step(0):  # Validate required attributes
        if not inp.get("product_name"):
            sample = _default_product()
            inp = {**sample, **{k: v for k, v in inp.items() if v}}
            used_sample = True
            ctx.note("no product supplied -> using bundled sample product (data/mock/sample_product.json)")
        if isinstance(inp.get("attributes"), str):
            try:
                inp["attributes"] = json.loads(inp["attributes"])
            except json.JSONDecodeError:
                raise NeedsInput("'attributes' must be a JSON object, e.g. {\"capacity\": \"20L\"}.", ["attributes"])
        missing = [k for k in REQUIRED if not inp.get(k)]
        ctx.note(f"missing attributes: {missing or 'none'}")
    facts = {k: inp.get(k) for k in REQUIRED if inp.get(k)}
    facts["attributes"] = inp.get("attributes") or {}

    with ctx.step(1):  # Create product description
        prompt = ("Write JSON with keys product_description (2-3 sentences), short_description (<=110 chars), "
                  "seo_title (<=60 chars), meta_description (<=155 chars) for this product.\nFACTS: " + json.dumps(facts))
        gen = ctx.call("llm", task="product_content", facts=facts, system=SYSTEM, prompt=prompt)
        content = gen["content"]
        bad = _invented(content, facts) if gen["source"] != "offline_fallback" else []
        if bad:   # guardrail: retry once with an explicit ban, then fall back to the fact-only template
            ctx.note(f"unsupported claims detected {bad} -> regenerating")
            strict = prompt + ("\nSTRICT: do NOT use these words or similar claims: " + ", ".join(bad) +
                               ". State only the given facts; no adjectives that are not in FACTS.")
            gen = ctx.call("llm", task="product_content", facts=facts, system=SYSTEM, prompt=strict)
            content = gen["content"]
            bad = _invented(content, facts) if gen["source"] != "offline_fallback" else []
            if bad:
                from app import llm_offline
                content = llm_offline.product_content(facts)
                gen = {"source": "offline_fallback (LLM kept inventing claims)", "content": content}
                ctx.note(f"still unsupported {bad} -> used fact-only template")

    with ctx.step(2):  # Generate short description
        ctx.note("short_description produced in the same structured LLM call")
    with ctx.step(3):  # Generate SEO title
        ctx.note("seo_title produced in the same structured LLM call")
    with ctx.step(4):  # Generate meta description
        check = ctx.call("text_validation", fields={k: content[k] for k in (
            "product_description", "short_description", "seo_title", "meta_description")},
            limits={"short_description": 110, "seo_title": 60, "meta_description": 155})
        fields = check["fields"]
        ctx.note("; ".join(check["issues"]) or "text validation passed")
    if missing:
        fields["product_description"] += (" [Missing information, not assumed: "
                                          + ", ".join(m.replace("_", " ") for m in missing) + ".]")
    summary = "\n".join(f"{k.replace('_', ' ').title()}: {v}" for k, v in fields.items())
    if missing:
        summary += "\nMissing product information (explicitly not invented): " + ", ".join(missing)
    return {"summary": summary, "data": {**fields, "missing_information": missing, "generated_by": gen["source"],
            "used_sample_product": used_sample, "facts_used": facts}}
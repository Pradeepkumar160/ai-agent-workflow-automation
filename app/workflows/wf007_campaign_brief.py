"""WF007 Marketing Campaign Brief (LLM messaging + deterministic structure)."""
import datetime as dt
import json
import re

from app.config import mock
from app.core.registry import InputSpec, workflow

MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
DATE_RANGE = (rf"((?:{MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s*\d{{4}})?|\d{{4}}-\d{{2}}-\d{{2}})\s*(?:-|–|to|until|through|and)\s*"
              rf"(?:{MONTH}\s+)?(?:\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s*\d{{4}})?|\d{{4}}-\d{{2}}-\d{{2}}))")
GOAL = (r"(?:goal|objective)\s*[:=]\s*([^;\n]+?)(?:;|\n|$)|\bto\s+((?:launch|promote|increase|boost|drive|grow|announce|"
        r"introduce|clear|re-?engage|build)\b.+?)(?=\s+(?:from|between|during|targeting|aimed|with|for)\b|[.,;]|$)")
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_date_range(text: str):
    """Best-effort parse of 'Oct 10-20', 'Oct 10 to Nov 2', '2026-10-10 to 2026-10-20'. Returns (start, end) or None."""
    iso = re.findall(r"\d{4}-\d{2}-\d{2}", text)
    try:
        if len(iso) >= 2:
            return dt.date.fromisoformat(iso[0]), dt.date.fromisoformat(iso[1])
        m = re.search(rf"({MONTH})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s*(\d{{4}}))?\s*(?:-|–|to|until|through|and)\s*(?:({MONTH})\s+)?(\d{{1,2}})",
                      text, flags=re.I)
        if not m:
            return None
        m1, d1, y1, m2, d2 = m.groups()
        year = int(y1) if y1 else dt.date.today().year
        mon1 = MONTHS[m1[:3].lower()]
        mon2 = MONTHS[m2[:3].lower()] if m2 else mon1
        return dt.date(year, mon1, int(d1)), dt.date(year if mon2 >= mon1 else year + 1, mon2, int(d2))
    except (ValueError, KeyError):
        return None


def _channels(audience: str, objective: str):
    a = (audience or "").lower()
    ch = [("Email newsletter", "Owned channel with direct reach to existing customers"),
          ("Website homepage banner + landing page", "Single destination for the offer")]
    if any(w in a for w in ("young", "gen z", "student", "teen", "travel", "millennial")):
        ch += [("Instagram / Reels", "Visual product discovery for a younger audience"),
               ("YouTube Shorts / short video", "Short-form video reach")]
    if any(w in a for w in ("professional", "business", "b2b", "corporate", "developer")):
        ch.append(("LinkedIn", "Professional audience targeting"))
    if any(w in a for w in ("famil", "parent", "home")):
        ch.append(("Facebook", "Family/household audience"))
    if objective in ("sales", "clearance", "launch"):
        ch.append(("Google Shopping / paid search", "Capture purchase-intent demand"))
    if objective == "retention":
        ch.append(("WhatsApp / SMS (opted-in)", "Re-engage existing customers"))
    if len(ch) == 2:
        ch.append(("Instagram / Facebook social posts", "Default broad-reach social channel"))
    return [{"channel": c, "why": w} for c, w in ch]


@workflow("WF007", inputs=[
    InputSpec("goal", "Campaign goal", required=True, pattern=GOAL,
              question="What is the campaign goal (e.g. 'launch the new collection')?"),
    InputSpec("dates", "Campaign dates", required=True, pattern=DATE_RANGE,
              question="What are the campaign dates (e.g. 'Oct 10 to Oct 20')?"),
    InputSpec("target_audience", "Target audience", pattern=r"(?:targeting|aimed at|audience\s*[:=])\s*([^;,.]+?)(?=\s+(?:with|from|between|during)\b|[;,.]|$)"),
    InputSpec("promotion", "Promotion", pattern=r"(?:promotion\s*[:=]\s*([^;]+)|(\d+%\s*(?:off|discount)[^,.;]*))"),
    InputSpec("products", "Product names (list)", kind="list"),
    InputSpec("products_path", "Product data", default=mock("products.csv"), kind="file"),
])
def run(ctx):
    inp = ctx.inputs
    with ctx.step(0):  # Validate inputs   (goal + dates are required before generating)
        ctx.note("goal and dates present")

    with ctx.step(1):  # Identify campaign objective
        pass  # classification happens together with messaging in the LLM call (step 3) – see below

    with ctx.step(2):  # Summarize products
        names = inp.get("products")
        if isinstance(names, str):
            names = [n.strip() for n in re.split(r"[;,]", names) if n.strip()]
        if names:
            table = ctx.call("product_data_reader", path=inp["products_path"], names=names)
            found = {r["product_name"].lower(): r for r in table.to_dict("records")}
            products = [{"name": n, "category": found.get(n.lower(), {}).get("category"),
                         "material": found.get(n.lower(), {}).get("material"), "color": found.get(n.lower(), {}).get("color")}
                        for n in names]
            ctx.note("products from request" + ("" if table is not None else ""))
        else:
            table = ctx.call("product_data_reader", path=inp["products_path"], collection="new")
            products = [{"name": r["product_name"], "category": r["category"], "material": r["material"],
                         "color": r["color"]} for r in table.to_dict("records")]
            ctx.note("no products supplied -> using the 'new' collection from product data")

    with ctx.step(3):  # Create messaging  (+ objective classification)
        facts = {"goal": inp["goal"], "products": [p["name"] for p in products],
                 "target_audience": inp.get("target_audience"), "promotion": inp.get("promotion")}
        system = ("You are a marketing strategist. Use only the facts given; do not invent offers, dates, prices or product claims.")
        prompt = ("Return JSON with objective_type (one of launch, awareness, sales, retention, clearance) and "
                  "key_messages (3-4 short strings) for this campaign.\nFACTS: " + json.dumps(facts))
        gen = ctx.call("llm", task="campaign_messaging", facts=facts, system=system, prompt=prompt)
        objective = str(gen["content"]["objective_type"]).lower()
        if objective not in ("launch", "awareness", "sales", "retention", "clearance"):
            objective = "awareness"
        ctx.steps[1].detail = f"objective = {objective}"

    with ctx.step(4):  # Create channel recommendations
        channels = _channels(inp.get("target_audience"), objective)

    with ctx.step(5):  # Create campaign checklist
        rng = parse_date_range(str(inp["dates"]))
        if rng:
            s, e = rng
            phases = [{"phase": "Pre-launch (teasers, creative sign-off)", "date": f"{s - dt.timedelta(days=7)} to {s - dt.timedelta(days=1)}"},
                      {"phase": "Campaign live", "date": f"{s} to {e}"},
                      {"phase": "Wrap-up & results review", "date": f"{e + dt.timedelta(days=1)} to {e + dt.timedelta(days=4)}"}]
        else:
            phases = [{"phase": "Campaign live", "date": str(inp["dates"])}]
            ctx.note("could not parse dates into a calendar range; used as provided")
        checklist = ["Confirm campaign objective and KPIs", "Finalise product list and stock availability",
                     "Approve messaging and creative", "Set up landing page and tracking links",
                     "Schedule channel posts / emails", "Launch campaign on the start date",
                     "Monitor performance daily and adjust", "Run post-campaign review"]
        if inp.get("promotion"):
            checklist.insert(2, f"Configure promotion in store: {inp['promotion']}")
    brief = {"objective": {"goal": inp["goal"], "type": objective},
             "audience": inp.get("target_audience") or "Not provided",
             "products": products, "promotion": inp.get("promotion") or "Not provided",
             "messaging": gen["content"]["key_messages"], "channels": channels,
             "timeline": {"dates": inp["dates"], "phases": phases}, "checklist": checklist,
             "generated_by": gen["source"]}
    summary = (f"CAMPAIGN BRIEF\nObjective: {inp['goal']} ({objective})\nAudience: {brief['audience']}\n"
               f"Products: {', '.join(p['name'] for p in products)}\nPromotion: {brief['promotion']}\n"
               "Messaging:\n" + "\n".join(f"  - {m}" for m in brief["messaging"]) +
               "\nChannels: " + ", ".join(c["channel"] for c in channels) +
               "\nTimeline:\n" + "\n".join(f"  - {p['phase']}: {p['date']}" for p in phases) +
               "\nChecklist:\n" + "\n".join(f"  [ ] {c}" for c in checklist))
    return {"summary": summary, "data": brief}

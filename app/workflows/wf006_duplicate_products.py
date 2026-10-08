"""WF006 Duplicate Product Detection."""
from itertools import combinations

from app.config import mock
from app.core.registry import InputSpec, workflow
from app.tools.text_tools import normalize_sku, normalize_text

ATTRS = ["category", "brand", "color", "material"]
NAME_MIN, SCORE_MIN, HIGH = 0.85, 0.85, 0.93


@workflow("WF006", inputs=[
    InputSpec("catalog_path", "Product catalog CSV", default=mock("catalog.csv"), kind="file", primary=True)])
def run(ctx):
    with ctx.step(0):  # Load products
        df = ctx.call("csv_reader", path=ctx.inputs["catalog_path"])
        ctx.call("data_validation", df=df, required_columns=["sku", "name"])
        df = df.fillna("").reset_index(drop=True)

    with ctx.step(1):  # Normalize names/SKUs
        df["_sku"] = df["sku"].map(normalize_sku)
        df["_name"] = df["name"].map(normalize_text)

    edges = []
    with ctx.step(2):  # Compare identifiers   (exact normalised SKU = definite duplicate)
        for i, j in combinations(range(len(df)), 2):
            if df.at[i, "_sku"] and df.at[i, "_sku"] == df.at[j, "_sku"]:
                edges.append({"a": i, "b": j, "type": "definite", "confidence": 1.0,
                              "matching_fields": ["sku"]})
        definite = {(e["a"], e["b"]) for e in edges}

    with ctx.step(3):  # Compare product attributes   (high attribute similarity = possible duplicate)
        similar = ctx.call("pairwise_similarity", names=df["name"].tolist(), min_score=NAME_MIN)
        for i, j, name_sim in similar:
            if (i, j) in definite:
                continue
            both = [a for a in ATTRS if df.at[i, a] and df.at[j, a]]
            same = [a for a in both if df.at[i, a].strip().lower() == df.at[j, a].strip().lower()]
            attr_ratio = len(same) / len(both) if both else 0.0
            score = 0.6 * name_sim + 0.4 * attr_ratio
            if score >= SCORE_MIN:
                edges.append({"a": i, "b": j, "type": "possible", "confidence": round(score, 3),
                              "matching_fields": ["name"] + same})

    with ctx.step(4):  # Group likely duplicates (union-find)
        parent = list(range(len(df)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for e in edges:
            parent[find(e["a"])] = find(e["b"])
        groups: dict[int, list[int]] = {}
        for idx in range(len(df)):
            groups.setdefault(find(idx), []).append(idx)

    with ctx.step(5):  # Assign confidence
        out = []
        for members in groups.values():
            if len(members) < 2:
                continue
            ges = [e for e in edges if e["a"] in members]
            conf = min(e["confidence"] for e in ges)
            types = {e["type"] for e in ges}
            kind = "definite" if types == {"definite"} else "possible" if types == {"possible"} else "mixed"
            level = "definite" if kind == "definite" else ("high" if conf >= HIGH else "medium")
            pairs = [{"a": df.at[e["a"], "sku"], "b": df.at[e["b"], "sku"], "match_type": e["type"],
                      "confidence": e["confidence"], "matching_fields": e["matching_fields"]} for e in ges]
            out.append({"match_type": kind, "confidence_level": level, "confidence_score": round(conf, 3),
                        "matching_fields": sorted({f for e in ges for f in e["matching_fields"]}),
                        "products": [{"sku": df.at[m, "sku"], "name": df.at[m, "name"]} for m in members],
                        "pairs": pairs})
        out.sort(key=lambda g: (-g["confidence_score"], g["products"][0]["sku"]))
    tag = {"definite": "DEFINITE", "possible": "POSSIBLE", "mixed": "DEFINITE SKU match + possible matches"}
    lines = [f"- [{tag[g['match_type']]}, {g['confidence_level']} confidence {g['confidence_score']:.2f}] "
             + " | ".join(f"{p['sku']} {p['name']}" for p in g["products"])
             + f" (matched on: {', '.join(g['matching_fields'])})" for g in out]
    summary = (f"{len(out)} duplicate group(s) found among {len(df)} products:\n" + "\n".join(lines)) \
        if out else f"No duplicates found among {len(df)} products."
    return {"summary": summary, "data": {"rules": "exact normalised SKU = definite; name similarity >= 0.85 and "
                                         "combined score >= 0.85 = possible", "groups": out}}

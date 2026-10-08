"""Behavioural tests for each of the 10 workflows, including the decision rules from the Excel file."""
import pandas as pd


def run(agent, request, inputs=None, wf=None):
    return agent.handle(request, inputs, workflow_id=wf).result


def test_wf001_restock_rule_and_boundary(agent):
    r = run(agent, "Which products need restocking?")
    assert r.status == "success"
    skus = {i["sku"] for i in r.data["items"]}
    assert skus == {"SKU-001", "SKU-003", "SKU-006", "SKU-008"}      # SKU-005 stock == min -> NOT flagged
    assert r.data["skipped_rows"][0]["sku"] == "SKU-010"             # non-numeric stock is reported, not a crash
    item = next(i for i in r.data["items"] if i["sku"] == "SKU-001")
    assert item["reorder_quantity"] == 16                            # 2 x 10 - 4


def test_wf001_threshold_override(agent):
    r = run(agent, "Which products are below a minimum stock threshold of 20?")
    skus = {i["sku"] for i in r.data["items"]}
    assert {"SKU-002", "SKU-009"} <= skus and "SKU-004" not in skus      # 18 and 15 are < 20; 25 is not


def test_wf002_threshold_boundary_and_unmatched(agent):
    r = run(agent, "Find products where vendor price differs by more than 10%.")
    flagged = {x["sku"] for x in r.data["results"] if x["exception"]}
    assert flagged == {"SKU-002", "SKU-005", "SKU-008"}              # SKU-003 is exactly 10% -> not flagged
    assert r.data["unmatched"]["internal_only"] == ["SKU-009"]
    assert r.data["unmatched"]["vendor_only"] == ["SKU-011"]
    assert r.data["unmatched"]["invalid_prices"] == ["SKU-010"]
    assert r.data["matched"] == 8                                    # ' sku-007 ' matched after normalisation


def test_wf002_custom_threshold(agent):
    r = run(agent, "Flag vendor price differences over 20%")
    assert {x["sku"] for x in r.data["results"] if x["exception"]} == {"SKU-008"}


def test_wf003_vendor_file_csv_and_xlsx(agent, tmp_path):
    for path in ("data/mock/vendor_products.csv", "data/mock/vendor_products.xlsx"):
        r = run(agent, "Process this vendor file", {"vendor_path": path}, wf="WF003")
        assert r.status == "success"
        assert (r.data["valid_rows"], r.data["invalid_rows"]) == (5, 3)
        assert r.data["column_mapping"]["item_code"] == "sku"
        assert [x["source_row"] for x in r.data["invalid_row_report"]] == [4, 5, 7]
    cleaned = pd.read_csv(tmp_path / "wf003_cleaned_vendor_file.csv")
    assert list(cleaned.columns[:2]) == ["sku", "product_name"] and len(cleaned) == 4
    assert cleaned["product_name"].str.strip().eq(cleaned["product_name"]).all()


def test_wf003_missing_required_column_fails_cleanly(agent, tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("foo,bar\n1,2\n")
    r = run(agent, "process vendor file", {"vendor_path": str(bad)}, wf="WF003")
    assert r.status == "failed" and "sku" in r.error.lower()


def test_wf003_missing_file(agent):
    r = run(agent, "process vendor file", {"vendor_path": "nope.csv"}, wf="WF003")
    assert r.status == "failed" and "not found" in r.error


def test_wf004_marks_missing_attributes_and_does_not_invent(agent):
    r = run(agent, "Generate SEO content for this product.")
    assert r.status == "success"
    assert r.data["missing_information"] == ["material"]
    assert "material" in r.data["product_description"].lower()       # flagged as missing...
    assert "nylon" not in r.data["product_description"].lower()      # ...and not invented
    assert len(r.data["seo_title"]) <= 60 and len(r.data["meta_description"]) <= 155


def test_wf004_complete_input_has_no_missing_note(agent):
    r = run(agent, "generate product content", {"product_name": "Travel Backpack", "category": "Bags", "material": "Nylon",
            "color": "Black", "target_audience": "travelers"}, wf="WF004")
    assert r.data["missing_information"] == [] and "Missing" not in r.summary.split("\n")[0]


def test_wf004_uses_llm_when_available_and_validates_length(make_agent):
    from tests.conftest import FakeLLM
    long = "x " * 200
    a = make_agent(FakeLLM([{"product_description": "Great bag.", "short_description": "Bag", "seo_title": long,
                             "meta_description": long}]))
    r = a.handle("Generate SEO content for this product.").result
    assert r.data["generated_by"] == "llm:fake-model"
    assert len(r.data["seo_title"]) <= 60 and len(r.data["meta_description"]) <= 155


def test_wf004_llm_garbage_falls_back(make_agent):
    from tests.conftest import FakeLLM
    a = make_agent(FakeLLM([{"unexpected": 1}]))
    r = a.handle("Generate SEO content for this product.").result
    assert r.status == "success" and r.data["generated_by"] == "offline_fallback"


def test_wf005_lookup_and_not_found(agent):
    r = run(agent, "Where is order ORD-1001?")
    o = r.data["orders"][0]
    assert o["order_status"] == "Shipped" and o["shipment"]["tracking_number"] == "TRK1001"
    miss = run(agent, "Where is order ORD-9999?")
    assert miss.status == "needs_input" and "another identifier" in miss.question


def test_wf005_email_and_no_shipment_and_bad_identifier(agent):
    assert len(run(agent, "status for alice@example.com").data["orders"]) == 2
    r = run(agent, "Where is order ORD-1002?")
    assert r.data["orders"][0]["shipment"] is None and "no shipment" in r.summary
    bad = run(agent, "order status", {"order_id": "banana"}, wf="WF005")
    assert bad.status == "needs_input"
    none = run(agent, "Where is my order?")
    assert none.status == "needs_input"


def test_wf005_retries_transient_api_failure(agent):
    from app.tools import api_tools
    api_tools._FLAKY["fail_next"] = 2
    r = run(agent, "Where is order ORD-1001?")
    assert r.status == "success"
    call = next(t for s in r.steps for t in s.tool_calls if t.tool == "order_api")
    assert call.attempts == 3


def test_wf005_gives_up_after_retries(agent):
    from app.tools import api_tools
    api_tools._FLAKY["fail_next"] = 10
    r = run(agent, "Where is order ORD-1001?")
    api_tools._FLAKY["fail_next"] = 0
    assert r.status == "failed" and "retries" in r.error


def test_wf006_definite_possible_and_non_duplicates(agent):
    r = run(agent, "Find likely duplicate products in the catalog.")
    groups = {frozenset(p["sku"] for p in g["products"]): g for g in r.data["groups"]}
    mouse = groups[frozenset({"P-1001", "p1001", "P-1002"})]
    assert mouse["match_type"] == "mixed" and any(p["match_type"] == "definite" for p in mouse["pairs"])
    assert groups[frozenset({"P-1003", "P-1004"})]["match_type"] == "possible"
    assert groups[frozenset({"P-1006", "P-1007"})]["match_type"] == "possible"
    all_skus = {s for k in groups for s in k}
    assert "P-1005" not in all_skus                                  # "Wireless Mouse Pad" is not a duplicate


def test_wf007_requires_goal_and_dates(agent):
    r = run(agent, "Create a campaign brief for the new collection.")
    assert r.status == "needs_input" and "goal" in r.question.lower() and "dates" in r.question.lower()
    assert not r.data


def test_wf007_full_brief(agent):
    r = run(agent, "Create a campaign brief to launch the new autumn collection from Oct 10 to Oct 20 "
                   "targeting young travelers with 20% off")
    assert r.status == "success"
    b = r.data
    assert b["objective"]["type"] == "launch" and b["audience"] == "young travelers"
    assert [p["date"] for p in b["timeline"]["phases"]][1] == "2026-10-10 to 2026-10-20"
    assert b["checklist"] and b["channels"] and b["messaging"]
    assert all(k in b for k in ("objective", "audience", "messaging", "channels", "timeline", "checklist"))


def test_wf007_marks_missing_optional_fields(agent):
    r = run(agent, "campaign brief", {"goal": "Raise awareness", "dates": "2026-11-01 to 2026-11-15"}, wf="WF007")
    assert r.data["audience"] == "Not provided" and r.data["promotion"] == "Not provided"


def test_wf008_dedupe_intent_mapping_priority(agent, tmp_path):
    r = run(agent, "Classify these keywords and map them to pages.")
    rows = {k["keyword"].lower(): k for k in r.data["keywords"]}
    assert r.data["duplicates_removed"] == 1 and "wireless mouse" in rows
    assert rows["buy wireless mouse online"]["intent"] == "transactional"
    assert rows["how to clean a mechanical keyboard"]["intent"] == "informational"
    assert rows["techstore login"]["intent"] == "navigational"
    assert rows["best travel backpack for carry on"]["intent"] == "commercial"
    assert rows["buy wireless mouse online"]["priority"] == "high"
    assert rows["yoga mat"]["category"] == "Unmapped"
    assert all(k["intent"] in ("informational", "commercial", "transactional", "navigational") for k in rows.values())
    assert (tmp_path / "wf008_keyword_report.csv").exists()


def test_wf008_repairs_invalid_llm_labels(make_agent):
    from tests.conftest import FakeLLM
    a = make_agent(FakeLLM([{"classifications": {"buy wireless mouse online": "banana"}}]))
    r = a.handle("Classify these keywords and map them to pages.").result
    assert r.status == "success"
    row = next(k for k in r.data["keywords"] if k["keyword"] == "buy wireless mouse online")
    assert row["intent"] == "transactional"


def test_wf009_ranking_and_reasoning(agent):
    r = run(agent, "Assign this urgent task to the best available developer by Friday.",
            {"task_description": "Build a Python REST API with a database backend"})
    assert r.status == "success" and r.data["employee"] == "Rohan"
    assert r.data["priority"] == "urgent" and r.data["deadline"] == "Friday" and r.data["reason"]
    names = [c["name"] for c in r.data["ranked_candidates"]]
    assert "Meera" not in names[:2] and "Sana" not in names          # role filter 'developer' excludes non-developers


def test_wf009_skips_fully_loaded_employee(agent):
    r = run(agent, "assign task", {"task_description": "automation testing in python", "role_filter": "qa"}, wf="WF009")
    assert r.status == "escalated"                                   # Meera has the skills but zero capacity


def test_wf009_escalates_when_nobody_fits(agent):
    r = run(agent, "assign task", {"task_description": "Train a computer vision model",
                                   "required_skills": ["computer vision"]}, wf="WF009")
    assert r.status == "escalated" and "ESCALATE" in r.summary


def test_wf009_needs_task(agent):
    r = run(agent, "Assign this urgent task to the best available developer.")
    assert r.status == "needs_input"


def test_wf010_flags_and_metrics(agent):
    r = run(agent, "Which workflows are failing most often?")
    by = {w["workflow_id"]: w for w in r.data["workflows"]}
    assert r.data["workflows"][0]["workflow_id"] == "WF002"          # sorted worst first
    assert by["WF002"]["flagged"] and by["WF002"]["failure_rate"] > 10
    assert by["WF005"]["flagged"] and by["WF005"]["failure_rate"] == 0  # flagged for slowness only
    assert not by["WF001"]["flagged"]
    assert r.data["frequent_errors"][0]["count"] >= r.data["frequent_errors"][-1]["count"]
    assert any(s["step"] == "shipment_lookup" for s in r.data["slow_steps"])
    assert r.data["recommendations"]

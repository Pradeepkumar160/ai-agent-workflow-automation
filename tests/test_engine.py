"""Engine / architecture behaviour: tracing, step coverage, errors, scalability."""
import shutil

import openpyxl
import pytest

from app.agent import WorkflowAgent
from app.core import registry
from app.core.registry import InputSpec, workflow
from app.core.tools import list_tools


def test_every_excel_step_is_traced_on_success(agent):
    """Each Excel step must appear in the trace as executed for the 'happy path' of every workflow."""
    runs = {
        "WF001": ("Which products need restocking?", {}), "WF002": ("validate vendor prices", {}),
        "WF003": ("process vendor file", {}), "WF004": ("generate seo content", {}),
        "WF005": ("Where is order ORD-1001?", {}), "WF006": ("find duplicate products", {}),
        "WF007": ("campaign brief", {"goal": "Launch", "dates": "Oct 10-20"}),
        "WF008": ("classify keywords", {}),
        "WF009": ("assign task", {"task_description": "Build python backend api"}),
        "WF010": ("performance report", {}),
    }
    for wid, (req, inputs) in runs.items():
        res = agent.handle(req, inputs, workflow_id=wid).result
        assert res.status == "success", (wid, res.error, res.summary)
        assert len(res.steps) == len(agent.catalog.get(wid).steps)
        assert all(s.status == "success" for s in res.steps), (wid, [(s.name, s.status) for s in res.steps])


def test_workflows_only_use_registered_tools(agent):
    names = set(list_tools())
    for res in (agent.handle(r, i, workflow_id=w).result for w, r, i in [
            ("WF001", "x", {}), ("WF005", "ORD-1001", {}), ("WF010", "x", {})]):
        for s in res.steps:
            for t in s.tool_calls:
                assert t.tool in names


def test_step_timing_and_tool_calls_recorded(agent):
    res = agent.handle("Which products need restocking?").result
    assert res.duration_ms >= 0 and res.steps[0].tool_calls[0].tool == "csv_reader"
    assert res.steps[0].tool_calls[0].summary.startswith("table with")


def test_missing_input_blocks_before_execution(agent):
    res = agent.handle("assign task").result
    assert res.status == "needs_input" and all(s.status == "not_run" for s in res.steps)


def test_unexpected_exception_is_contained(agent, monkeypatch):
    spec = registry.get_spec("WF001")
    monkeypatch.setattr(spec, "run", lambda ctx: 1 / 0)
    res = agent.handle("Which products need restocking?").result
    assert res.status == "failed" and "ZeroDivisionError" in res.error


def test_defaults_are_reported(agent):
    res = agent.handle("Which products need restocking?").result
    assert "inventory_path" in res.defaults_used


def test_manual_workflow_override(agent):
    resp = agent.handle("anything at all", workflow_id="WF010")
    assert resp.selection.method == "manual" and resp.result.workflow_id == "WF010"


def test_ambiguous_request_returns_no_result(agent):
    resp = agent.handle("hello there")
    assert resp.result is None and resp.selection.clarification


def test_explicit_inputs_override_extracted(agent):
    res = agent.handle("Where is order ORD-1001?", {"order_id": "ORD-1003"}).result
    assert res.data["orders"][0]["order_id"] == "ORD-1003"


# ---- scalability: add an 11th workflow with ONE Excel row + ONE plugin function --------------------
def test_adding_an_11th_workflow_needs_only_excel_row_and_one_function(tmp_path):
    xlsx = tmp_path / "wf.xlsx"
    shutil.copy("data/AI_Agent_Workflow_Assessment.xlsx", xlsx)
    wb = openpyxl.load_workbook(xlsx)
    ws = wb["Workflows"]
    ws.append(["WF011", "Supplier Lead Time Analysis", "User asks to analyse supplier delivery lead times",
               "Supplier delivery CSV", "Load deliveries → calculate lead time → flag slow suppliers",
               "Flag suppliers above 7 days", "CSV reader; calculator", "Lead-time report"])
    wb.save(xlsx)

    @workflow("WF011", inputs=[InputSpec("days", "threshold days", default=7, kind="number")])
    def lead_time(ctx):
        with ctx.step(0):
            df = ctx.call("csv_reader", path="data/mock/inventory.csv")
        with ctx.step(1):
            n = len(df)
        with ctx.step(2):
            slow = n
        return {"summary": f"{slow} suppliers analysed", "data": {"n": n}}

    try:
        a = WorkflowAgent(excel_path=xlsx, output_dir=tmp_path)
        resp = a.handle("analyse supplier delivery lead times")
        assert resp.selection.workflow_id == "WF011"
        assert resp.result.status == "success" and [s.status for s in resp.result.steps] == ["success"] * 3
        # existing workflows still route correctly
        assert a.handle("Where is order ORD-1001?").selection.workflow_id == "WF005"
    finally:
        registry._SPECS.pop("WF011", None)


def test_workflow_in_excel_without_plugin_reports_not_implemented(tmp_path):
    xlsx = tmp_path / "wf.xlsx"
    shutil.copy("data/AI_Agent_Workflow_Assessment.xlsx", xlsx)
    wb = openpyxl.load_workbook(xlsx)
    wb["Workflows"].append(["WF012", "Warehouse Slotting Optimisation", "User asks to optimise warehouse slotting",
                            "Slot map", "Load slots → optimise", "n/a", "solver", "Slot plan"])
    wb.save(xlsx)
    a = WorkflowAgent(excel_path=xlsx, output_dir=tmp_path)
    res = a.handle("optimise warehouse slotting").result
    assert res.status == "not_implemented"

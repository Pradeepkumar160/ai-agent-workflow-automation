import pandas as pd
import pytest

from app.config import EXCEL_PATH
from app.workflow.loader import load_workflows_from_excel


def test_excel_loads_10_workflows():
    wfs = load_workflows_from_excel(EXCEL_PATH)
    assert list(wfs) == [f"WF{i:03d}" for i in range(1, 11)]
    assert all(w.steps for w in wfs.values())


def test_every_excel_workflow_has_an_implementation(agent):
    from app.core.registry import get_spec
    assert all(get_spec(i) for i in agent.catalog.ids())


def test_missing_excel_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_workflows_from_excel(tmp_path / "nope.xlsx")


def test_excel_test_questions_route_correctly(agent):
    q = pd.read_excel(EXCEL_PATH, sheet_name="Test_Questions")
    for r in q.itertuples():
        sel = agent.router.select(r.Test_Request)
        assert sel.workflow_id == r.Workflow_ID, (r.Test_Request, sel)


@pytest.mark.parametrize("text,expected", [
    ("what needs reordering from the warehouse stock", "WF001"),
    ("compare our prices with the supplier price list", "WF002"),
    ("clean this vendor csv and tell me the bad rows", "WF003"),
    ("write a product description and meta description", "WF004"),
    ("track order status for ORD-1001", "WF005"),
    ("are there any duplicate products in the catalog", "WF006"),
    ("draft a marketing campaign brief", "WF007"),
    ("classify keywords by search intent", "WF008"),
    ("assign the task to an employee", "WF009"),
    ("generate a workflow performance report", "WF010"),
])
def test_paraphrased_requests_route(agent, text, expected):
    assert agent.router.select(text).workflow_id == expected


def test_vague_request_asks_for_clarification(agent):
    sel = agent.router.select("hello there")
    assert sel.workflow_id is None and sel.clarification


def test_empty_request_rejected(agent):
    with pytest.raises(ValueError):
        agent.router.select("   ")


def test_llm_router_used_when_available(make_agent):
    from tests.conftest import FakeLLM
    a = make_agent(FakeLLM(route={"workflow_id": "WF006", "confidence": 0.9, "reason": "dupes"}))
    sel = a.router.select("anything")
    assert (sel.workflow_id, sel.method) == ("WF006", "llm")


def test_llm_router_invalid_id_falls_back_to_lexical(make_agent):
    from tests.conftest import FakeLLM
    a = make_agent(FakeLLM(route={"workflow_id": "WF999", "confidence": 1}))
    sel = a.router.select("Which products need restocking?")
    assert sel.workflow_id == "WF001" and sel.method == "lexical" and "fallback" in sel.reason


def test_llm_router_outage_falls_back(make_agent):
    from tests.conftest import FakeLLM
    a = make_agent(FakeLLM(fail=True))
    assert a.router.select("Where is order ORD-1001?").workflow_id == "WF005"

import json
from pathlib import Path

import pytest

from app.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_cli_json_output(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr("app.agent.agent.OUTPUT_DIR", tmp_path)
    assert main(["Where is order ORD-1001?", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["selection"]["workflow_id"] == "WF005" and out["result"]["status"] == "success"


def test_cli_text_output_shows_workflow_steps_result(capsys):
    main(["Which products need restocking?"])
    text = capsys.readouterr().out
    assert "Selected Workflow: WF001" in text and "Steps Executed:" in text and "Result:" in text


def test_cli_list(capsys):
    assert main(["--list"]) == 0
    assert capsys.readouterr().out.count("implemented") >= 10


def test_streamlit_app_loads_and_runs():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
    assert not at.exception
    at.text_area[0].set_value("Which products need restocking?")
    at.button[0].click().run()
    assert not at.exception
    assert any("WF001" in m.value for m in at.metric) or any("WF001" in str(x.value) for x in at.metric)

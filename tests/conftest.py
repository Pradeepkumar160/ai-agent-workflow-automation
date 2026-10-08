import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent import WorkflowAgent  # noqa: E402
from app.llm import LLMClient  # noqa: E402


class FakeLLM(LLMClient):
    """Scripted LLM so online code paths are testable without network/API keys.
    route=<dict> answers the router prompt (None -> router call fails -> lexical fallback);
    responses=[...] are returned, in order, to workflow generation calls; extraction calls get {}."""

    def __init__(self, responses=None, route=None, fail=False):
        super().__init__(api_key="test-key", model="fake-model")
        self.responses, self.route, self.fail, self.calls = list(responses or []), route, fail, []

    def chat_json(self, system, user):
        from app.llm import LLMUnavailable
        self.calls.append((system, user))
        if self.fail:
            raise LLMUnavailable("simulated outage")
        if "workflow router" in system:
            if self.route is None:
                raise LLMUnavailable("no scripted route")
            return self.route
        if "Extract input values" in system:
            return {}
        return self.responses.pop(0) if self.responses else {}


@pytest.fixture()
def agent(tmp_path):
    return WorkflowAgent(llm=LLMClient(api_key=""), output_dir=tmp_path)


@pytest.fixture()
def make_agent(tmp_path):
    def _make(llm):
        return WorkflowAgent(llm=llm, output_dir=tmp_path)
    return _make

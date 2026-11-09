import pytest

from backend.agents import llm as llm_module
from backend.agents.mocks import FakeLLM, fake_search


@pytest.fixture(autouse=True)
def _isolate_llm(monkeypatch):
    """Aucun test ne doit atteindre un vrai LLM ni dépendre de l'environnement."""
    llm_module.set_llm(None)
    for var in [v for v in __import__("os").environ if v.startswith("LLM_")]:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(llm_module, "_transport", None)
    yield
    llm_module.set_llm(None)


@pytest.fixture
def plan():
    return {"request_id": "REQ-20261106-0001", "intent": "procedure", "domain": "public_services",
            "subdomain": "national_identity_card", "agents": ["procedure"], "needs_clarification": False}


@pytest.fixture
def llm():
    return FakeLLM()


@pytest.fixture
def search():
    return fake_search

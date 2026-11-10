import json
from pathlib import Path

import pytest

from backend.agents import run_agents, validate_draft
from backend.agents.cli import main
from backend.agents.mocks import FakeLLM, fake_search

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "t2"


def test_cli_mock_outputs_valid_json(capsys):
    assert main(["Quels documents pour ma première CNI ?", "--mock"]) == 0
    drafts = json.loads(capsys.readouterr().out)
    assert len(drafts) == 1 and validate_draft(drafts[0]) == []


def test_cli_merge_and_plan_file(capsys):
    plan_file = str(EXAMPLES / "routing_plans_mock.json")
    assert main(["Quels documents pour ma première CNI ?", "--mock", "--plan", plan_file,
                 "--plan-index", "0", "--merge"]) == 0
    merged = json.loads(capsys.readouterr().out)
    assert merged["agent"] == "merged" and merged["request_id"] == "REQ-20261106-0001"


def test_cli_reports_errors(capsys):
    assert main(["   ", "--mock"]) == 1
    assert "Erreur" in capsys.readouterr().err


def test_cli_show_prompt(capsys):
    assert main(["Combien coûte la CNI ?", "--mock", "--show-prompt"]) == 0
    assert "PASSAGES" in capsys.readouterr().err


def test_mock_files_are_valid_t1_contract_and_all_run():
    cases = json.loads((EXAMPLES / "routing_plans_mock.json").read_text(encoding="utf-8"))
    assert len(cases) >= 10
    ids = [c["routing_plan"]["request_id"] for c in cases]
    assert len(set(ids)) == len(ids)
    for case in cases:
        plan = case["routing_plan"]
        assert set(plan) == {"request_id", "intent", "domain", "subdomain", "agents", "needs_clarification"}
        drafts = run_agents(case["question"], plan, language=case["language"],
                            search_fn=fake_search, llm_fn=FakeLLM())
        assert drafts and all(validate_draft(d) == [] for d in drafts), case["question"]


def test_passages_mock_has_phase2_format():
    passages = json.loads((EXAMPLES / "passages_mock.json").read_text(encoding="utf-8"))
    assert len(passages) == 4
    assert all({"rank", "score", "distance", "chunk_id", "document_id", "text", "source_page"} <= set(p) for p in passages)
    drafts = run_agents("CNI ?", {"request_id": "R-1", "intent": "procedure", "agents": ["procedure"]},
                        search_fn=lambda q, k: passages, llm_fn=FakeLLM())
    assert validate_draft(drafts[0]) == []


def test_example_output_is_a_valid_draft():
    path = EXAMPLES / "output_agents_example.json"
    if not path.exists():
        pytest.skip("exemple de sortie absent")
    assert validate_draft(json.loads(path.read_text(encoding="utf-8"))) == []

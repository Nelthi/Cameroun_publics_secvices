"""Tests de T4 avec les mocks de T1, T2 et T3."""
import re
import time

import pytest
from fastapi.testclient import TestClient

from app import audit
from app.main import app

client = TestClient(app)
Q_OK = "Quelles sont les pièces pour la CNI ?"
Q_OUT = "Combien coûte un permis de conduire ?"


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIT_DB", str(tmp_path / "audit.db"))
    for name in ("T1_IMPL", "T2_IMPL", "T3_IMPL", "STAGE_TIMEOUT"):
        monkeypatch.delenv(name, raising=False)


def ask(q):
    return client.post("/ask", json={"question": q})


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_approved_answer_with_sources_and_audit():
    r = ask(Q_OK)
    body = r.json()
    assert r.status_code == 200 and body["status"] == "approved"
    assert re.fullmatch(r"REQ-\d{8}-[0-9A-F]{6}", body["request_id"])
    assert body["sources"] == [{"document_id": "DOC-EXEMPLE-CNI", "source_page": 1}]
    row = client.get(f"/audit/{body['request_id']}").json()
    assert row["status"] == "approved" and row["error"] is None
    assert row["routing_json"]["request_id"] == body["request_id"]
    assert row["validation_json"]["checks"]["grounded"] is True
    assert row["duration_ms"] >= 0


def test_refused_answer_records_gap():
    r = ask(Q_OUT)
    body = r.json()
    assert r.status_code == 200 and body["status"] == "refused" and body["sources"] == []
    gaps = client.get("/gaps").json()
    assert len(gaps) == 1 and gaps[0]["count"] == 1 and "permis" in gaps[0]["topic"]


def test_same_gap_is_grouped():
    ask(Q_OUT)
    ask(Q_OUT)
    assert client.get("/gaps").json()[0]["count"] == 2


def test_needs_clarification_skips_t2_t3():
    body = ask("CNI ?").json()
    assert body["status"] == "needs_clarification" and body["sources"] == []
    row = client.get(f"/audit/{body['request_id']}").json()
    assert row["agent_outputs_json"] is None and row["validation_json"] is None


def test_stage_exception_gives_503_and_audit(monkeypatch):
    def boom(*a):
        raise RuntimeError("LLM injoignable")
    monkeypatch.setattr("app.stages.run_agents", boom)
    r = ask(Q_OK)
    body = r.json()
    assert r.status_code == 503 and body["status"] == "error"
    assert "indisponible" in body["answer"]
    row = client.get(f"/audit/{body['request_id']}").json()
    assert row["status"] == "error" and "T2" in row["error"] and "LLM injoignable" in row["error"]


def test_contract_violation_names_stage_and_field(monkeypatch):
    monkeypatch.setattr("app.stages.run_agents",
                        lambda routing, q: {"request_id": routing["request_id"], "answerDraft": "x"})
    body = ask(Q_OK).json()
    assert body["status"] == "error"
    row = client.get(f"/audit/{body['request_id']}").json()
    assert "T2" in row["error"] and "answer_draft" in row["error"]
    assert row["agent_outputs_json"] is not None  # sortie brute gardée pour le débogage


def test_timeout(monkeypatch):
    monkeypatch.setenv("STAGE_TIMEOUT", "0.2")
    monkeypatch.setattr("app.stages.route_question", lambda payload: time.sleep(1))
    r = ask(Q_OK)
    assert r.status_code == 503
    row = client.get(f"/audit/{r.json()['request_id']}").json()
    assert "T1" in row["error"] and "délai" in row["error"]


def test_invalid_questions_rejected():
    assert client.post("/ask", json={"question": "   "}).status_code == 422
    assert client.post("/ask", json={"question": "a" * 501}).status_code == 422
    assert client.post("/ask", json={}).status_code == 422


def test_phone_number_masked_in_audit_only():
    body = ask("Mon numéro 677 12 34 56 est-il valable pour la CNI ?").json()
    row = client.get(f"/audit/{body['request_id']}").json()
    assert "677" not in row["question"] and "[NUMÉRO MASQUÉ]" in row["question"]


def test_mask_does_not_touch_request_ids_or_short_numbers():
    assert audit.mask_sensitive("REQ-20261107-ABC123") == "REQ-20261107-ABC123"
    assert audit.mask_sensitive("page 12, 2 photos") == "page 12, 2 photos"


def test_unknown_request_id_404():
    assert client.get("/audit/REQ-00000000-000000").status_code == 404

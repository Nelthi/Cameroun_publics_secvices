"""Phase 3 de bout en bout : API (T4) -> routage (T1) -> agents (T2) -> guardrails (T3).

Le document est ingéré avec la VRAIE chaîne de la Phase 2 (T1 -> T2 -> T3 de la Phase 2). Seuls la
recherche vectorielle (modèle bge-m3, trop lourd pour un test) et le LLM sont remplacés :
  * recherche : recouvrement de mots sur les vrais fragments, au format exact de backend.rag.search ;
  * LLM : backend.pipeline.phase3.demo_llm (extraction du passage le plus proche).
"""
import json
import re
import unicodedata
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.agents import set_llm
from backend.knowledge_base.collectors import DocumentMetadata
from backend.pipeline import phase3
from backend.pipeline.run import run_pipeline

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "01_CNI" / "Plaquette-20-Mai-2025-FR-ok.pdf"
STOP = set("le la les de du des un une et en au aux pour par sur est il elle ma mon mes que qui quel quelle "
           "puis je peut peuvent faut comment combien temps faire dans ou ce cette son sa ses se ne pas".split())


def _tokens(text):
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return {w for w in re.findall(r"[a-z0-9]+", text) if w not in STOP and len(w) > 2}


@pytest.fixture(scope="module")
def ingested(tmp_path_factory):
    data = tmp_path_factory.mktemp("p3") / "data"
    meta = DocumentMetadata(title="Plaquette CNI", institution="DGSN", date="2025-05-20",
                            domain="public_services", subdomain="national_identity_card")
    res = run_pipeline(PDF, meta, data_root=data, build_faiss=False)
    doc = json.loads(Path(res["chunks"]).read_text(encoding="utf-8"))
    return doc["document_id"], doc["chunks"]


@pytest.fixture
def client(ingested, tmp_path, monkeypatch):
    document_id, chunks = ingested

    def search(query, top_k=4):  # même format que backend.rag.search
        wanted = _tokens(query)
        scored = sorted(((len(wanted & _tokens(c["text"])) / max(len(wanted), 1), c) for c in chunks),
                        key=lambda item: -item[0])
        return [{"rank": rank, "score": round(min(0.95, 0.15 + 0.8 * s), 4), "chunk_id": c["chunk_id"],
                 "document_id": document_id, "source_page": c["source_page"], "text": c["text"]}
                for rank, (s, c) in enumerate(scored[:top_k], start=1)]

    import backend.rag as rag
    monkeypatch.setattr(rag, "search", search)
    for name, spec in phase3.IMPLS.items():
        monkeypatch.setenv(name, spec)
    monkeypatch.setenv("PHASE3_LLM", "demo")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("AUDIT_DB", str(tmp_path / "audit.db"))
    from app.main import app
    yield TestClient(app)
    set_llm(None)


def test_question_answered_with_source(client, ingested):
    document_id, _ = ingested
    body = client.post("/ask", json={"question": "Comment faire le pré-enrôlement en ligne pour la CNI ?"}).json()
    assert body["status"] == "approved" and "idcam.cm" in body["answer"]
    assert body["sources"] and all(s["document_id"] == document_id for s in body["sources"])
    audit = client.get(f"/audit/{body['request_id']}").json()
    assert audit["routing_json"]["intent"] == "procedure" and audit["routing_json"]["agents"] == ["procedure"]
    assert audit["agent_outputs_json"]["citations"] and audit["validation_json"]["status"] == "approved"
    assert audit["status"] == "approved" and audit["error"] is None


def test_off_topic_is_refused_and_logged_as_gap(client):
    body = client.post("/ask", json={"question": "Quel est le score du match de foot ?"}).json()
    assert body["status"] == "refused" and body["sources"] == []
    assert any("foot" in gap["topic"] for gap in client.get("/gaps").json())


def test_phone_number_is_never_stored_or_repeated(client):
    question = "Mon numéro de téléphone est 699123456, où retirer ma CNI ?"
    body = client.post("/ask", json={"question": question}).json()
    assert body["status"] in {"partial", "refused"}
    assert "699123456" not in body["answer"]
    stored = json.dumps(client.get(f"/audit/{body['request_id']}").json(), ensure_ascii=False)
    assert "699123456" not in stored


def test_without_llm_the_api_degrades_cleanly(client, monkeypatch):
    """Aucun LLM configuré : pas de plantage, une réponse polie et une trace dans l'audit."""
    set_llm(None)
    monkeypatch.delenv("PHASE3_LLM", raising=False)
    body = client.post("/ask", json={"question": "Quelles pièces pour la CNI ?"}).json()
    assert body["status"] in {"refused", "error"} and body["sources"] == []
    assert client.get(f"/audit/{body['request_id']}").status_code == 200


def test_plan_of_t1_is_accepted_by_t2_for_every_intent():
    """Contrat T1 -> T2 : tous les noms d'agents que T1 peut produire sont connus de T2."""
    from backend.agents import canonical_agent_name
    from backend.orchestration import route_question
    for q in ["Quelles pièces pour la CNI ?", "Quels textes de loi encadrent la CNI ?", "Bonjour",
              "Quel est le score du match ?", "Mes données personnelles sont-elles protégées ?"]:
        plan = route_question({"request_id": "REQ-20261108-0001", "question": q, "language": "fr",
                               "timestamp": "2026-11-08T10:00:00"})
        for agent in plan["agents"]:
            canonical_agent_name(agent)

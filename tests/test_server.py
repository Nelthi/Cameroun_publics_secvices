"""API de démonstration (utilisateur + administrateur), de bout en bout, sans réseau.

Remplacés : modèle d'embedding (faux), Groq (faux modèle) et recherche vectorielle de la phase 3
(recouvrement de mots sur les vrais fragments). Tout le reste est le vrai code des membres.
"""
import json
import re
import time
import unicodedata
import zlib
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "01_CNI" / "Plaquette-20-Mai-2025-FR-ok.pdf"
META = {"title": "Plaquette CNI", "institution": "DGSN", "date": "2025-05-20",
        "domain": "public_services", "subdomain": "national_identity_card"}
STOP = set("le la les de du des un une et en au aux pour par sur est il elle ma mon mes que qui quel quelle "
           "puis je peut peuvent faut comment combien temps faire dans ou ce cette son sa ses se ne pas".split())


class FakeEmbedder:
    normalize = True

    def encode(self, texts):
        out = np.zeros((len(texts), 384), dtype="float32")
        for row, text in enumerate(texts):
            for tok in re.findall(r"\w+", text.lower()):
                out[row, zlib.crc32(tok.encode()) % 384] += 1.0
        return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)


def fake_groq(prompt, **_):
    """Faux modèle : propose des métadonnées ou des débuts de fragments selon la consigne reçue."""
    if "cataloguer" in prompt:
        return json.dumps({"title": "Guide IA", "institution": "DGSN", "date": "2025-01-02",
                           "domain": "public_services", "subdomain": "Passport", "summary": "résumé"})
    return json.dumps({"starts": [0, 3]})


def tokens(text):
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return {w for w in re.findall(r"[a-z0-9]+", text) if w not in STOP and len(w) > 2}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("AUDIT_DB", str(tmp_path / "audit.db"))
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("PHASE3_LLM", "demo")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    from backend.ai import groq
    from backend.server import main, services

    monkeypatch.setattr(groq, "ask", fake_groq)
    monkeypatch.setattr(services, "get_embedder", lambda: FakeEmbedder())

    def search(query, top_k=4):  # même format que backend.rag.search
        wanted, rows = tokens(query), []
        for item in services.list_chunks(limit=500)["items"]:
            score = len(wanted & tokens(item["text"])) / max(len(wanted), 1)
            rows.append((score, item))
        rows.sort(key=lambda r: -r[0])
        return [{"rank": i, "score": round(min(0.95, 0.15 + 0.8 * s), 4), "chunk_id": c["chunk_id"],
                 "document_id": c["document_id"], "source_page": c["source_page"], "text": c["text"]}
                for i, (s, c) in enumerate(rows[:top_k], start=1)]

    import backend.rag as rag
    monkeypatch.setattr(rag, "search", search)
    yield TestClient(main.app)
    from backend.agents import set_llm
    set_llm(None)


def wait(client, job, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        data = client.get(f"/api/admin/jobs/{job['id']}").json()
        if data["status"] in {"done", "error"}:
            return data
        time.sleep(0.05)
    raise AssertionError("tâche trop longue")


def upload(client, files, metas=None, **form):
    payload = [("files", (name, content, "application/octet-stream")) for name, content in files]
    data = {"metadata": json.dumps(metas or [])}
    data.update({k: str(v).lower() for k, v in form.items()})
    return client.post("/api/admin/documents", files=payload, data=data)


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["tasks"]["T1_IMPL"].endswith("phase3:route_question")


def test_multi_upload_duplicate_and_auto_metadata(client):
    text = ("Passeport. " + "Pièces à fournir pour le passeport ordinaire. " * 6).encode()
    res = upload(client, [("plaquette.pdf", PDF.read_bytes()), ("guide.txt", text)], [META]).json()
    assert [r["ok"] for r in res["results"]] == [True, True] and res["stored"] == 2
    assert res["results"][0]["subdomain"] == "national_identity_card"
    assert res["results"][1]["metadata_source"] == "groq" and res["results"][1]["subdomain"] == "passport"
    again = upload(client, [("plaquette.pdf", PDF.read_bytes())], [META]).json()
    assert again["results"][0]["duplicate"] is True and again["stored"] == 0
    docs = client.get("/api/admin/documents").json()
    assert len(docs) == 2 and not any(d["extracted"] or d["chunked"] or d["indexed"] for d in docs)


def test_bad_files_are_reported_per_file(client):
    res = upload(client, [("notes.xyz", b"abc"), ("ok.txt", b"Texte " * 40)],
                 [META, {**META, "title": "ok"}], auto_metadata=False).json()
    assert res["results"][0]["ok"] is False and res["results"][0]["error"]
    assert res["results"][1]["ok"] is True


def test_suggest_metadata_endpoint(client):
    res = client.post("/api/admin/suggest-metadata", files={"file": ("a.txt", b"Titre\nContenu du document " * 5)})
    body = res.json()
    assert body["ai"] is True and body["title"] == "Guide IA" and body["subdomain"] == "passport"


def test_phases_native_then_ai_then_index(client):
    upload(client, [("plaquette.pdf", PDF.read_bytes())], [META])
    ident = client.get("/api/admin/documents").json()[0]["document_id"]
    # chunk avant extraction : erreur claire, pas de plantage
    early = wait(client, client.post("/api/admin/run/chunk", json={"mode": "native"}).json())
    assert early["status"] == "error" and "extrait" in " ".join(early["log"])
    assert wait(client, client.post("/api/admin/run/extract", json={}).json())["status"] == "done"
    assert client.get(f"/api/admin/documents/{ident}/text").json()["character_count"] > 1000

    native = wait(client, client.post("/api/admin/run/chunk", json={"mode": "native"}).json())
    assert native["status"] == "done"
    n_native = client.get("/api/admin/chunks", params={"document_id": ident, "limit": 200}).json()["total"]
    assert client.get("/api/admin/documents").json()[0]["chunk_mode"] == "native"

    ai = wait(client, client.post("/api/admin/run/chunk", json={"mode": "ai", "document_ids": [ident]}).json())
    assert ai["status"] == "done" and "IA Groq" in " ".join(ai["log"])
    chunks = client.get("/api/admin/chunks", params={"document_id": ident, "limit": 200}).json()
    assert client.get("/api/admin/documents").json()[0]["chunk_mode"] == "ai"
    assert chunks["total"] > 0 and all(len(c["text"]) <= 800 for c in chunks["items"]) and chunks["total"] != n_native

    index = wait(client, client.post("/api/admin/run/index", json={}).json())
    assert index["status"] == "done" and index["result"]["index"]["dim"] == 384
    vec = client.get("/api/admin/vectors", params={"limit": 3}).json()
    assert vec["built"] and vec["total"] == chunks["total"] and len(vec["items"][0]["first_values"]) == 8
    ov = client.get("/api/admin/overview").json()
    assert ov["documents"] == 1 and ov["indexed"] == 1 and ov["vectors"] == chunks["total"]


def test_ai_chunking_failure_is_explicit(client, monkeypatch):
    from backend.ai import groq

    upload(client, [("plaquette.pdf", PDF.read_bytes())], [META])
    wait(client, client.post("/api/admin/run/extract", json={}).json())

    def broken(prompt, **_):
        raise RuntimeError("quota dépassé")

    monkeypatch.setattr(groq, "ask", broken)
    job = wait(client, client.post("/api/admin/run/chunk", json={"mode": "ai"}).json())
    assert job["status"] == "error" and "quota" in " ".join(job["log"])
    assert client.get("/api/admin/documents").json()[0]["chunked"] is False  # rien produit en silence


def test_run_all_and_chat(client):
    upload(client, [("plaquette.pdf", PDF.read_bytes())], [META])
    ident = client.get("/api/admin/documents").json()[0]["document_id"]
    job = wait(client, client.post("/api/admin/run/all", json={"mode": "native"}).json())
    assert job["status"] == "done"
    doc = client.get("/api/admin/documents").json()[0]
    assert doc["extracted"] and doc["chunked"] and doc["indexed"]

    headers = {"X-User-Id": "alice"}
    conv = client.post("/api/chat/conversations", json={}, headers=headers).json()
    reply = client.post(f"/api/chat/conversations/{conv['id']}/messages",
                        json={"text": "Comment faire le pré-enrôlement en ligne pour la CNI ?"}, headers=headers).json()
    assert reply["role"] == "assistant" and reply["status"] == "approved" and "idcam.cm" in reply["content"]
    assert reply["sources"] and all(s["document_id"] == ident for s in reply["sources"])
    assert all(s["title"] == "Plaquette CNI" and s["source_page"] >= 1 for s in reply["sources"])
    full = client.get(f"/api/chat/conversations/{conv['id']}", headers=headers).json()
    assert [m["role"] for m in full["messages"]] == ["user", "assistant"] and full["title"].startswith("Comment faire")
    assert [c["id"] for c in client.get("/api/chat/conversations", headers=headers).json()] == [conv["id"]]
    assert client.get(f"/api/chat/conversations/{conv['id']}", headers={"X-User-Id": "bob"}).status_code == 404
    assert client.get("/api/chat/conversations", headers={"X-User-Id": "bob"}).json() == []
    audit = client.get("/api/admin/audit").json()
    assert audit["requests"][0]["request_id"] == reply["request_id"]
    assert client.delete(f"/api/chat/conversations/{conv['id']}", headers=headers).status_code == 204


def test_admin_token(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    assert client.get("/api/admin/overview").status_code == 401
    assert client.get("/api/admin/overview", headers={"X-Admin-Token": "secret"}).status_code == 200
    assert client.get("/api/chat/conversations").status_code == 200  # l'interface utilisateur reste ouverte

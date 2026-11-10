"""T2 branché sur le VRAI code de la Phase 2 (VectorStore + FAISS), avec le faux embedder
des tests de T4 : prouve que le format renvoyé par search() est bien celui qu'attendent les agents."""
import json
import re
import zlib
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("faiss")

from backend.agents import merge_drafts, run_agents, validate_draft  # noqa: E402
from backend.rag.chunk_loader import load_chunks  # noqa: E402
from backend.rag.vector_store import VectorStore, build_index  # noqa: E402

CHUNKS = Path(__file__).resolve().parents[2] / "data" / "chunks"


class FakeEmbedder:
    normalize = True

    def encode(self, texts):
        out = np.zeros((len(texts), 384), dtype="float32")
        for row, text in enumerate(texts):
            for tok in re.findall(r"\w+", text.lower()):
                out[row, zlib.crc32(tok.encode()) % 384] += 1.0
        return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)


@pytest.fixture(scope="module")
def store():
    index, mapping = build_index(load_chunks(CHUNKS), FakeEmbedder())
    return VectorStore(index, mapping, FakeEmbedder())


def test_agents_consume_real_search_output(store, plan):
    seen = {}

    def llm(prompt):
        seen["prompt"] = prompt
        return "Pièces à fournir : un acte de naissance [1]."

    plan["agents"] = ["procedure", "juridique"]
    drafts = run_agents("quelles sont les pièces à fournir pour la CNI", plan,
                        search_fn=lambda q, k: store.search(q, k), llm_fn=llm, top_k=3)
    assert len(drafts) == 2 and all(validate_draft(d) == [] for d in drafts)
    first = drafts[0]
    top = store.search("quelles sont les pièces à fournir pour la CNI", 3)[0]
    # Le renvoi [1] désigne bien le premier passage de search(), avec son document et sa page.
    assert first["citations"][0] == {"chunk_id": top["chunk_id"], "document_id": top["document_id"],
                                     "source_page": top["source_page"]}
    assert first["retrieval"]["top_score"] == top["score"] and first["retrieval"]["n_chunks"] == 3
    assert top["text"] in seen["prompt"]
    merged = merge_drafts(drafts)
    assert validate_draft(merged) == [] and len(merged["citations"]) == 1  # même passage cité par les deux agents
    json.dumps(merged, ensure_ascii=False)  # sérialisable tel quel pour T3 / T4


def test_default_search_is_backend_rag_search(monkeypatch, plan):
    """Sans search_fn, les agents appellent backend.rag.search(question, top_k=...)."""
    import backend.rag as rag

    calls = []
    monkeypatch.setattr(rag, "search", lambda query, top_k=4: calls.append((query, top_k)) or [
        {"rank": 1, "score": 0.7, "distance": 0.6, "chunk_id": "D-C1", "document_id": "D",
         "text": "La CNI coûte 10.000 FCFA.", "source_page": 2}])
    (draft,) = run_agents("Combien coûte la CNI ?", plan, llm_fn=lambda p: "10.000 FCFA [1].")
    assert calls == [("Combien coûte la CNI ?", 4)]
    assert draft["citations"] == [{"chunk_id": "D-C1", "document_id": "D", "source_page": 2}]


def test_missing_index_gives_error_draft_with_clear_message(monkeypatch, plan, tmp_path):
    import backend.rag as rag
    from backend.rag.vector_store import VectorStore as VS

    monkeypatch.setattr(rag, "_store", None)
    monkeypatch.setattr(VS, "from_disk", classmethod(lambda cls, *a, **k: (_ for _ in ()).throw(
        FileNotFoundError("faiss.index introuvable. Lancez d'abord : python -m backend.rag.build_index"))))
    (draft,) = run_agents("Combien coûte la CNI ?", plan, llm_fn=lambda p: "x")
    assert draft["meta"]["kind"] == "error" and "build_index" in draft["meta"]["error"]

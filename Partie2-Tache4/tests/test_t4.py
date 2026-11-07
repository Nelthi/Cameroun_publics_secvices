"""Tests T4. Un faux embedder évite de télécharger le modèle : les tests
sont rapides et vérifient le CONTRAT (formats, tailles, erreurs)."""
import json
import os
import re
import zlib
from pathlib import Path

import numpy as np
import pytest

from backend.rag.chunk_loader import load_chunks
from backend.rag.vector_store import VectorStore, build_index, load_index, save_index

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "chunks"


class FakeEmbedder:
    """Sac de mots haché en 384 dimensions, normalisé (déterministe)."""
    normalize = True

    def encode(self, texts):
        out = np.zeros((len(texts), 384), dtype="float32")
        for row, text in enumerate(texts):
            for tok in re.findall(r"\w+", text.lower()):
                out[row, zlib.crc32(tok.encode()) % 384] += 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.maximum(norms, 1e-9)


@pytest.fixture(scope="module")
def chunks():
    return load_chunks(SAMPLES)


@pytest.fixture(scope="module")
def store(chunks):
    index, mapping = build_index(chunks, FakeEmbedder())
    return VectorStore(index, mapping, FakeEmbedder())


def test_loader_reads_all_samples(chunks):
    assert len(chunks) == 5
    assert set(chunks[0]) == {"chunk_id", "document_id", "text", "source_page"}


def test_loader_rejects_missing_field(tmp_path):
    bad = {"document_id": "D", "chunks": [{"chunk_id": "D-C1", "text": "abc"}]}
    (tmp_path / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="source_page"):
        load_chunks(tmp_path)


def test_loader_skips_empty_and_duplicates(tmp_path):
    doc = {"document_id": "D", "chunks": [
        {"chunk_id": "D-C1", "text": "bonjour", "source_page": 1},
        {"chunk_id": "D-C1", "text": "doublon", "source_page": 1},
        {"chunk_id": "D-C2", "text": "   ", "source_page": 1},
    ]}
    (tmp_path / "d.json").write_text(json.dumps(doc), encoding="utf-8")
    assert [c["chunk_id"] for c in load_chunks(tmp_path)] == ["D-C1"]


def test_contract_index_and_mapping(store, chunks):
    assert store.index.ntotal == len(chunks) and store.index.d == 384
    assert list(store.mapping) == [str(i) for i in range(len(chunks))]
    for entry in store.mapping.values():
        assert set(entry) == {"chunk_id", "document_id", "text", "source_page"}


def test_save_and_load_roundtrip(store, tmp_path):
    save_index(store.index, store.mapping, tmp_path / "f.index", tmp_path / "m.json")
    index, mapping = load_index(tmp_path / "f.index", tmp_path / "m.json")
    assert index.ntotal == store.index.ntotal and mapping == store.mapping


def test_search_finds_relevant_chunk(store):
    top = store.search("quelles sont les pièces à fournir pour la CNI", top_k=4)
    assert top[0]["chunk_id"] == "DOC-EXEMPLE-CNI-C001"
    assert top[0]["source_page"] == 1 and len(top) == 4
    top = store.search("frais de timbre fiscal")
    assert top[0]["chunk_id"] == "DOC-EXEMPLE-CNI-C003"


def test_search_top_k_larger_than_index(store):
    assert len(store.search("passeport", top_k=50)) == 5


def test_search_rejects_bad_input(store):
    with pytest.raises(ValueError):
        store.search("   ")
    with pytest.raises(ValueError):
        store.search("cni", top_k=0)


def test_load_index_missing_files(tmp_path):
    with pytest.raises(FileNotFoundError, match="build_index"):
        load_index(tmp_path / "x.index", tmp_path / "x.json")


@pytest.mark.skipif(not os.getenv("RUN_SLOW"), reason="définir RUN_SLOW=1 (utilise le vrai modèle)")
def test_real_model_semantic_search(chunks):
    from backend.rag.embedder import Embedder
    emb = Embedder()
    index, mapping = build_index(chunks, emb)
    top = VectorStore(index, mapping, emb).search("documents nécessaires pour obtenir ma carte d'identité", 2)
    assert top[0]["document_id"] in {"DOC-EXEMPLE-CNI", "DOC-EXEMPLE-PASSEPORT"}

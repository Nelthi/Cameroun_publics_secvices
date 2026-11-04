import json
import pickle
import sys
import types

import numpy as np
import pytest

from backend.knowledge_base.vector_store import FaissVectorStore
from backend.knowledge_base.vector_store.exceptions import (
    EmbeddingFilesError,
    VectorSearchError,
)


class FakeIndexFlatIP:
    def __init__(self, dimension):
        self.d = dimension
        self.vectors = np.empty((0, dimension), dtype=np.float32)
        self.ntotal = 0

    def add(self, vectors):
        self.vectors = np.vstack([self.vectors, vectors]).astype(np.float32)
        self.ntotal = len(self.vectors)

    def search(self, queries, k):
        scores = queries @ self.vectors.T
        order = np.argsort(-scores, axis=1)[:, :k]
        return np.take_along_axis(scores, order, axis=1), order.astype(np.int64)


def fake_faiss_module():
    module = types.ModuleType("faiss")
    module.IndexFlatIP = FakeIndexFlatIP

    def write_index(index, path):
        with open(path, "wb") as stream:
            pickle.dump(index, stream)

    def read_index(path):
        with open(path, "rb") as stream:
            return pickle.load(stream)

    module.write_index = write_index
    module.read_index = read_index
    return module


class FakeEncoder:
    def encode(self, texts, **kwargs):
        mapping = {
            "documents pour la CNI": [1.0, 0.0, 0.0],
            "paiement des impôts": [0.0, 1.0, 0.0],
            "Quels documents fournir pour la CNI ?": [1.0, 0.0, 0.0],
        }
        return np.asarray([mapping[text] for text in texts], dtype=np.float32)


def create_embedding(data_root, doc_id, model_name, vectors, texts):
    folder = data_root / "embeddings" / "public_services" / "cni" / doc_id
    folder.mkdir(parents=True)
    np.save(folder / "vectors.npy", np.asarray(vectors, dtype=np.float32))
    manifest = {
        "document_id": doc_id,
        "metadata": {"domain": "public_services", "subdomain": "cni", "title": "Guide CNI"},
        "embedding": {"status": "embedded", "model_name": model_name},
        "items": [
            {"chunk_id": f"{doc_id}-CHUNK-{i}", "chunk_index": i,
             "page_number": i + 1, "text": text}
            for i, text in enumerate(texts)
        ],
    }
    (folder / "metadata.json").write_text(json.dumps(manifest), encoding="utf-8")


@pytest.fixture
def setup_store(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "faiss", fake_faiss_module())
    model = "test/multilingual-model"
    create_embedding(
        tmp_path, "DOC-AAAAAAAAAAAA", model,
        [[1, 0, 0], [0, 1, 0]],
        ["documents pour la CNI", "paiement des impôts"],
    )
    store = FaissVectorStore(tmp_path, model_name=model, encoder=FakeEncoder())
    return tmp_path, store


def test_build_index_and_search_returns_most_similar_first(setup_store):
    _, store = setup_store
    built = store.build_index()
    assert built["vector_count"] == 2
    assert built["dimension"] == 3

    results = store.search("Quels documents fournir pour la CNI ?", top_k=2)
    assert len(results) == 2
    assert results[0].text == "documents pour la CNI"
    assert results[0].score == pytest.approx(1.0)
    assert results[0].page_number == 1


def test_search_rejects_empty_query(setup_store):
    _, store = setup_store
    store.build_index()
    with pytest.raises(VectorSearchError):
        store.search("   ")


def test_build_rejects_mixed_models(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "faiss", fake_faiss_module())
    create_embedding(tmp_path, "DOC-AAAAAAAAAAAA", "model-A", [[1, 0]], ["A"])
    create_embedding(tmp_path, "DOC-BBBBBBBBBBBB", "model-B", [[0, 1]], ["B"])
    store = FaissVectorStore(tmp_path, model_name="model-A", encoder=FakeEncoder())
    with pytest.raises(EmbeddingFilesError):
        store.build_index()


def test_build_rejects_vector_manifest_count_mismatch(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "faiss", fake_faiss_module())
    create_embedding(tmp_path, "DOC-AAAAAAAAAAAA", "model-A", [[1, 0]], ["A", "B"])
    store = FaissVectorStore(tmp_path, model_name="model-A", encoder=FakeEncoder())
    with pytest.raises(EmbeddingFilesError):
        store.build_index()

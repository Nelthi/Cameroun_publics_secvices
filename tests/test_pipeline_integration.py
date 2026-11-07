"""Test de bout en bout T1 -> T2 -> T3 -> T4 (faux embedder : pas de téléchargement)."""
import json
import re
import zlib
from pathlib import Path

import numpy as np

from backend.knowledge_base.collectors import DocumentMetadata
from backend.pipeline import run_pipeline
from backend.rag.vector_store import VectorStore, load_index

ROOT = Path(__file__).resolve().parents[1]


class FakeEmbedder:
    normalize = True

    def encode(self, texts):
        out = np.zeros((len(texts), 384), dtype="float32")
        for row, text in enumerate(texts):
            for tok in re.findall(r"\w+", text.lower()):
                out[row, zlib.crc32(tok.encode()) % 384] += 1.0
        return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)


def meta(title):
    return DocumentMetadata(title=title, institution="DGSN", date="2026-11-04",
                            domain="public_services", subdomain="national_identity_card")


def test_txt_chain(tmp_path):
    src = tmp_path / "cni.txt"
    src.write_text("Pour la carte nationale d'identité, fournir un acte de naissance. "
                   "Les frais sont de 2800 FCFA. " * 40, encoding="utf-8")
    res = run_pipeline(src, meta("CNI"), data_root=tmp_path / "data", embedder=FakeEmbedder())
    chunks = json.loads(Path(res["chunks"]).read_text(encoding="utf-8"))
    assert chunks["document_id"] == res["document_id"] and res["chunk_count"] > 1
    assert all(len(c["text"]) <= 800 for c in chunks["chunks"])
    index, mapping = load_index(tmp_path / "data/indexes/faiss.index",
                                tmp_path / "data/indexes/chunk_mapping.json")
    assert index.ntotal == res["chunk_count"] == res["vectors"]
    hits = VectorStore(index, mapping, FakeEmbedder()).search("frais carte identité", top_k=2)
    assert hits and res["document_id"] in json.dumps(hits, ensure_ascii=False)


def test_real_pdf_chain(tmp_path):
    pdf = next((ROOT / "01_CNI").glob("2ce7f303*.pdf"))
    res = run_pipeline(pdf, meta("PDF CNI"), data_root=tmp_path / "data", embedder=FakeEmbedder())
    assert res["chunk_count"] > 0 and res["vectors"] == res["chunk_count"]


def test_duplicate_is_detected(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("contenu identique " * 30, encoding="utf-8")
    first = run_pipeline(src, meta("A"), data_root=tmp_path / "data", embedder=FakeEmbedder())
    second = run_pipeline(src, meta("A"), data_root=tmp_path / "data", embedder=FakeEmbedder())
    # T1 refuse le doublon et renvoie l'identifiant existant (règle du guide).
    assert second["duplicate"] is True and second["document_id"] == first["document_id"]

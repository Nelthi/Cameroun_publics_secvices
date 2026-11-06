import json
from pathlib import Path

import numpy as np
import pytest

from backend.knowledge_base.embeddings import (
    ChunkFileNotFoundError,
    EmbeddingGenerator,
    InvalidChunkFileError,
    InvalidEmbeddingConfigError,
)

DOC_ID = "DOC-ABCDEF123456"


class FakeEncoder:
    def encode(self, texts, **kwargs):
        # Petit vecteur déterministe pour tester le pipeline sans télécharger un modèle.
        return np.array([[len(text), sum(map(ord, text)) % 101, 1] for text in texts], dtype=np.float32)


def write_chunks(root: Path, *, status="chunked", chunks=None):
    folder = root / "chunks" / "public_services" / "national_identity_card"
    folder.mkdir(parents=True)
    payload = {
        "document_id": DOC_ID,
        "metadata": {"title": "Procédure CNI", "domain": "public_services", "subdomain": "national_identity_card"},
        "chunking": {"status": status, "chunk_count": len(chunks or [])},
        "chunks": chunks if chunks is not None else [
            {"chunk_id": "CHK-ABCDEF123456-0001", "document_id": DOC_ID, "chunk_index": 1,
             "page_number": 2, "text": "Pièces nécessaires pour une première CNI.", "character_count": 42},
            {"chunk_id": "CHK-ABCDEF123456-0002", "document_id": DOC_ID, "chunk_index": 2,
             "page_number": 3, "text": "Le demandeur fournit un justificatif.", "character_count": 38},
        ],
    }
    (folder / f"{DOC_ID}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_embedding_generation_saves_vectors_and_manifest(tmp_path):
    write_chunks(tmp_path)
    result = EmbeddingGenerator(tmp_path, encoder=FakeEncoder()).embed_document(DOC_ID)
    output = tmp_path / result.output_dir
    vectors = np.load(output / "vectors.npy", allow_pickle=False)
    manifest = json.loads((output / "metadata.json").read_text(encoding="utf-8"))

    assert result.status == "embedded"
    assert vectors.shape == (2, 3)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)
    assert manifest["items"][0]["chunk_id"] == "CHK-ABCDEF123456-0001"
    assert manifest["items"][0]["page_number"] == 2
    assert manifest["embedding"]["normalization"] == "l2"


def test_missing_chunks_file_raises(tmp_path):
    with pytest.raises(ChunkFileNotFoundError):
        EmbeddingGenerator(tmp_path, encoder=FakeEncoder()).embed_document(DOC_ID)


def test_invalid_chunk_status_is_rejected(tmp_path):
    write_chunks(tmp_path, status="empty")
    with pytest.raises(InvalidChunkFileError):
        EmbeddingGenerator(tmp_path, encoder=FakeEncoder()).embed_document(DOC_ID)


def test_empty_chunk_is_rejected(tmp_path):
    write_chunks(tmp_path, chunks=[{"chunk_id": "CHK-1", "document_id": DOC_ID, "text": " "}])
    with pytest.raises(InvalidChunkFileError):
        EmbeddingGenerator(tmp_path, encoder=FakeEncoder()).embed_document(DOC_ID)


def test_invalid_batch_size_is_rejected(tmp_path):
    with pytest.raises(InvalidEmbeddingConfigError):
        EmbeddingGenerator(tmp_path, batch_size=0, encoder=FakeEncoder())


def test_wrong_document_reference_is_rejected(tmp_path):
    write_chunks(tmp_path, chunks=[{"chunk_id": "CHK-1", "document_id": "DOC-000000000000", "text": "Texte"}])
    with pytest.raises(InvalidChunkFileError):
        EmbeddingGenerator(tmp_path, encoder=FakeEncoder()).embed_document(DOC_ID)

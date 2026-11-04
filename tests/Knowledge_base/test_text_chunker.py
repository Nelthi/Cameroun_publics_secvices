import json
from pathlib import Path

import pytest

from backend.knowledge_base.chunkers import (
    InvalidChunkingConfigError,
    ProcessedDocumentNotFoundError,
    TextChunker,
)


DOC_ID = "DOC-ABCDEF123456"


def write_processed(root: Path, *, text: str, page_number=None, status="processed"):
    folder = root / "processed" / "public_services" / "national_identity_card"
    folder.mkdir(parents=True)
    payload = {
        "document_id": DOC_ID,
        "source": {"original_filename": "procedure.txt", "file_format": "txt"},
        "metadata": {
            "title": "Procédure CNI",
            "domain": "public_services",
            "subdomain": "national_identity_card",
            "institution": "DGSN",
        },
        "content": {"segments": [{"segment_id": "SEG-0001", "page_number": page_number, "text": text}]},
        "processing": {"status": status},
    }
    (folder / f"{DOC_ID}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def test_chunk_document_creates_json_and_keeps_metadata(tmp_path):
    write_processed(tmp_path, text="Premier paragraphe.\n\nDeuxième paragraphe.", page_number=2)
    result = TextChunker(tmp_path, chunk_size=100, overlap=10).chunk_document(DOC_ID)
    output = tmp_path / result.output_path
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result.status == "chunked"
    assert result.chunk_count >= 1
    assert payload["metadata"]["institution"] == "DGSN"
    assert all(chunk["page_number"] == 2 for chunk in payload["chunks"])
    assert all(chunk["document_id"] == DOC_ID for chunk in payload["chunks"])


def test_long_text_is_split_and_chunks_respect_size(tmp_path):
    text = " ".join([f"Phrase numéro {i} avec des informations administratives." for i in range(30)])
    write_processed(tmp_path, text=text)
    result = TextChunker(tmp_path, chunk_size=180, overlap=30).chunk_document(DOC_ID)
    payload = json.loads((tmp_path / result.output_path).read_text(encoding="utf-8"))

    assert result.chunk_count > 1
    assert all(len(chunk["text"]) <= 180 for chunk in payload["chunks"])


def test_chunks_have_stable_sequential_indexes(tmp_path):
    write_processed(tmp_path, text=" ".join(["information" * 10] * 15))
    result = TextChunker(tmp_path, chunk_size=100, overlap=10).chunk_document(DOC_ID)
    payload = json.loads((tmp_path / result.output_path).read_text(encoding="utf-8"))
    indexes = [chunk["chunk_index"] for chunk in payload["chunks"]]
    assert indexes == list(range(1, len(indexes) + 1))


def test_missing_processed_document_raises(tmp_path):
    with pytest.raises(ProcessedDocumentNotFoundError):
        TextChunker(tmp_path).chunk_document(DOC_ID)


def test_invalid_overlap_configuration_raises(tmp_path):
    with pytest.raises(InvalidChunkingConfigError):
        TextChunker(tmp_path, chunk_size=100, overlap=100)


def test_unprocessed_document_is_rejected(tmp_path):
    write_processed(tmp_path, text="Texte", status="needs_ocr_or_review")
    from backend.knowledge_base.chunkers import InvalidProcessedDocumentError
    with pytest.raises(InvalidProcessedDocumentError):
        TextChunker(tmp_path).chunk_document(DOC_ID)


def test_overlapping_chunks_share_context(tmp_path):
    text = " ".join([f"mot{i}" for i in range(120)])
    write_processed(tmp_path, text=text)
    result = TextChunker(tmp_path, chunk_size=150, overlap=40).chunk_document(DOC_ID)
    payload = json.loads((tmp_path / result.output_path).read_text(encoding="utf-8"))
    chunks = [item["text"] for item in payload["chunks"]]

    assert len(chunks) > 1
    assert any(set(chunks[i].split()) & set(chunks[i + 1].split()) for i in range(len(chunks) - 1))

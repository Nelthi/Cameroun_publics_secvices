import zipfile

import pytest

from backend.knowledge_base.collectors import (
    DocumentCollector, DocumentMetadata, DuplicateDocumentError,
    InvalidDocumentError, UnsupportedFormatError
)


def metadata(**overrides):
    values = dict(
        title="Document test",
        domain="public_services",
        subdomain="national_identity_card",
        institution="DGSN",
        document_type="official_procedure",
        reliability="official",
        verification_date="2026-11-03",
    )
    values.update(overrides)
    return DocumentMetadata(**values)


def test_import_txt_and_persist_metadata(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("Procédure de test", encoding="utf-8")
    collector = DocumentCollector(data_root=tmp_path / "data")

    result = collector.import_document(source, metadata())

    assert result.document_id.startswith("DOC-")
    assert (tmp_path / "data" / result.stored_path).exists()
    saved = collector.get_document(result.document_id)
    assert saved["metadata"]["institution"] == "DGSN"
    assert saved["file_format"] == "txt"


def test_reject_duplicate_content(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("Même contenu", encoding="utf-8")
    collector = DocumentCollector(data_root=tmp_path / "data")
    collector.import_document(source, metadata())

    with pytest.raises(DuplicateDocumentError):
        collector.import_document(source, metadata(title="Autre titre"))


def test_reject_unsupported_extension(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("a,b", encoding="utf-8")
    collector = DocumentCollector(data_root=tmp_path / "data")

    with pytest.raises(UnsupportedFormatError):
        collector.import_document(source, metadata())


def test_reject_invalid_pdf_signature(tmp_path):
    source = tmp_path / "fake.pdf"
    source.write_bytes(b"not a pdf")
    collector = DocumentCollector(data_root=tmp_path / "data")

    with pytest.raises(InvalidDocumentError):
        collector.import_document(source, metadata())


def test_reject_empty_file(tmp_path):
    source = tmp_path / "empty.txt"
    source.write_text("", encoding="utf-8")
    collector = DocumentCollector(data_root=tmp_path / "data")

    with pytest.raises(InvalidDocumentError):
        collector.import_document(source, metadata())

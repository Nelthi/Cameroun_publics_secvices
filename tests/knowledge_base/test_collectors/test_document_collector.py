"""Tests du cœur T1 — DocumentCollector.

Couverture :
- OK (txt / pdf / docx)
- invalide (extension, signature, absent, trop gros)
- vide
- doublon
- métadonnées
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

from backend.knowledge_base.collectors import (
    DocumentCollector,
    DocumentMetadata,
    InvalidDocumentError,
    MetadataValidationError,
    UnsupportedFormatError,
)


def make_metadata(**overrides) -> DocumentMetadata:
    values = {
        "title": "Plaquette CNI",
        "institution": "DGSN",
        "date": "2026-11-04",
        "domain": "public_services",
        "subdomain": "national_identity_card",
    }
    values.update(overrides)
    return DocumentMetadata(**values)


# ---------------------------------------------------------------------------
# Cas OK
# ---------------------------------------------------------------------------


def test_ok_import_txt_stores_file_and_sqlite(
    collector: DocumentCollector,
    txt_file: Path,
    meta: DocumentMetadata,
    tmp_path: Path,
) -> None:
    result = collector.import_document(txt_file, meta)

    assert result.document_id.startswith("DOC-")
    assert len(result.document_id) == 12
    assert result.status == "stored"
    assert result.is_duplicate is False
    assert result.domain == "public_services"
    assert result.institution == "DGSN"
    assert result.original_filename == "guide.txt"
    assert result.stored_path.startswith(
        "data/raw/public_services/national_identity_card/"
    )
    assert result.stored_path.endswith(".txt")
    assert (tmp_path / result.stored_path).is_file()

    saved = collector.get_document(result.document_id)
    assert saved is not None
    assert saved["sha256"] == result.sha256
    assert saved["title"] == "Plaquette CNI"
    assert saved["document_date"] == "2026-11-04"
    assert saved["status"] == "stored"

    payload = result.to_dict()
    assert set(payload) >= {
        "document_id",
        "sha256",
        "original_filename",
        "stored_path",
        "upload_date",
        "domain",
        "institution",
        "status",
    }
    assert "is_duplicate" not in payload


def test_ok_import_pdf_computes_sha256(
    collector: DocumentCollector,
    pdf_file: Path,
    meta: DocumentMetadata,
) -> None:
    result = collector.import_document(pdf_file, meta)

    assert result.status == "stored"
    assert result.stored_path.endswith(".pdf")
    assert result.sha256 == hashlib.sha256(pdf_file.read_bytes()).hexdigest()


def test_ok_import_docx(
    collector: DocumentCollector,
    docx_file: Path,
    meta: DocumentMetadata,
) -> None:
    result = collector.import_document(docx_file, meta)

    assert result.status == "stored"
    assert result.stored_path.endswith(".docx")


def test_ok_original_filename_override(
    collector: DocumentCollector,
    tmp_path: Path,
    meta: DocumentMetadata,
) -> None:
    source = tmp_path / "tmp.bin"
    source.write_text("contenu texte", encoding="utf-8")

    result = collector.import_document(
        source,
        meta,
        original_filename="guide_officiel.txt",
    )

    assert result.original_filename == "guide_officiel.txt"
    assert result.stored_path.endswith(".txt")


def test_ok_list_documents_filters_by_domain(
    collector: DocumentCollector,
    tmp_path: Path,
) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("doc A", encoding="utf-8")
    b.write_text("doc B", encoding="utf-8")

    collector.import_document(
        a,
        make_metadata(domain="public_services", subdomain="cni"),
    )
    collector.import_document(
        b,
        make_metadata(domain="education", subdomain="exams"),
    )

    all_docs = collector.list_documents()
    public_only = collector.list_documents(domain="public_services")

    assert len(all_docs) == 2
    assert len(public_only) == 1
    assert public_only[0]["domain"] == "public_services"


# ---------------------------------------------------------------------------
# Doublon
# ---------------------------------------------------------------------------


def test_duplicate_same_path_returns_existing_id(
    collector: DocumentCollector,
    txt_file: Path,
    meta: DocumentMetadata,
    tmp_path: Path,
) -> None:
    first = collector.import_document(txt_file, meta)
    second = collector.import_document(
        txt_file,
        make_metadata(title="Autre titre"),
    )

    assert second.is_duplicate is True
    assert second.document_id == first.document_id
    assert second.sha256 == first.sha256
    assert second.to_dict()["is_duplicate"] is True

    files_only = [
        path for path in (tmp_path / "data" / "raw").rglob("*") if path.is_file()
    ]
    assert len(files_only) == 1


def test_duplicate_different_filenames_same_content(
    collector: DocumentCollector,
    tmp_path: Path,
    meta: DocumentMetadata,
) -> None:
    first_path = tmp_path / "copie1.txt"
    second_path = tmp_path / "copie2.txt"
    content = "Contenu strictement identique"
    first_path.write_text(content, encoding="utf-8")
    second_path.write_text(content, encoding="utf-8")

    first = collector.import_document(first_path, meta)
    second = collector.import_document(second_path, meta)

    assert second.is_duplicate is True
    assert second.document_id == first.document_id


# ---------------------------------------------------------------------------
# Fichier vide / invalide
# ---------------------------------------------------------------------------


def test_empty_file_rejected(
    collector: DocumentCollector,
    tmp_path: Path,
    meta: DocumentMetadata,
) -> None:
    source = tmp_path / "empty.txt"
    source.write_text("", encoding="utf-8")

    with pytest.raises(InvalidDocumentError):
        collector.import_document(source, meta)


def test_missing_file_rejected(
    collector: DocumentCollector,
    tmp_path: Path,
    meta: DocumentMetadata,
) -> None:
    with pytest.raises(InvalidDocumentError):
        collector.import_document(tmp_path / "absent.txt", meta)


def test_unsupported_extension_rejected(
    collector: DocumentCollector,
    tmp_path: Path,
    meta: DocumentMetadata,
) -> None:
    source = tmp_path / "data.csv"
    source.write_text("a,b", encoding="utf-8")

    with pytest.raises(UnsupportedFormatError):
        collector.import_document(source, meta)


def test_invalid_pdf_signature_rejected(
    collector: DocumentCollector,
    tmp_path: Path,
    meta: DocumentMetadata,
) -> None:
    source = tmp_path / "fake.pdf"
    source.write_bytes(b"not a pdf")

    with pytest.raises(InvalidDocumentError):
        collector.import_document(source, meta)


def test_invalid_docx_archive_rejected(
    collector: DocumentCollector,
    tmp_path: Path,
    meta: DocumentMetadata,
) -> None:
    source = tmp_path / "fake.docx"
    source.write_bytes(b"PK\x03\x04not-a-real-docx")

    with pytest.raises(InvalidDocumentError):
        collector.import_document(source, meta)


def test_docx_without_document_xml_rejected(
    collector: DocumentCollector,
    tmp_path: Path,
    meta: DocumentMetadata,
) -> None:
    source = tmp_path / "incomplete.docx"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")

    with pytest.raises(InvalidDocumentError):
        collector.import_document(source, meta)


def test_oversized_file_rejected(tmp_path: Path, meta: DocumentMetadata) -> None:
    source = tmp_path / "big.txt"
    source.write_text("x" * 100, encoding="utf-8")
    collector = DocumentCollector(data_root=tmp_path / "data", max_file_size=50)

    with pytest.raises(InvalidDocumentError):
        collector.import_document(source, meta)


def test_invalid_domain_path_segment_rejected(
    collector: DocumentCollector,
    txt_file: Path,
) -> None:
    with pytest.raises(InvalidDocumentError):
        collector.import_document(
            txt_file,
            make_metadata(domain="...", subdomain="cni"),
        )


# ---------------------------------------------------------------------------
# Métadonnées
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    ["title", "institution", "date", "domain", "subdomain"],
)
def test_metadata_blank_field_rejected(
    collector: DocumentCollector,
    txt_file: Path,
    field: str,
) -> None:
    with pytest.raises(MetadataValidationError):
        collector.import_document(txt_file, make_metadata(**{field: "   "}))


@pytest.mark.parametrize(
    "bad_date",
    ["04/11/2026", "2026/11/04", "11-04-2026", "not-a-date", ""],
)
def test_metadata_invalid_date_rejected(
    collector: DocumentCollector,
    txt_file: Path,
    bad_date: str,
) -> None:
    with pytest.raises(MetadataValidationError):
        collector.import_document(txt_file, make_metadata(date=bad_date))


@pytest.mark.parametrize(
    "good_date",
    ["2026-11-04", "2026-11-04T10:00:00", "2025-05-20T14:30:00"],
)
def test_metadata_iso_date_accepted(
    collector: DocumentCollector,
    tmp_path: Path,
    good_date: str,
) -> None:
    source = tmp_path / f"doc_{good_date.replace(':', '-')}.txt"
    source.write_text(f"contenu {good_date}", encoding="utf-8")

    result = collector.import_document(source, make_metadata(date=good_date))

    assert result.status == "stored"
    saved = collector.get_document(result.document_id)
    assert saved is not None
    assert saved["document_date"] == good_date


def test_get_unknown_document_returns_none(collector: DocumentCollector) -> None:
    assert collector.get_document("DOC-DOESNOTEXIST") is None

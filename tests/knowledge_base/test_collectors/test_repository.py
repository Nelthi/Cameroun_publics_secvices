"""Tests SQLite — DocumentRepository (T1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.knowledge_base.database import DocumentRepository


def _record(**overrides) -> dict:
    base = {
        "document_id": "DOC-AAAA1111",
        "sha256": "a" * 64,
        "original_filename": "guide.txt",
        "stored_path": "data/raw/public_services/cni/DOC-AAAA1111.txt",
        "upload_date": "2026-11-05T08:00:00",
        "domain": "public_services",
        "subdomain": "cni",
        "institution": "DGSN",
        "title": "Guide",
        "document_date": "2026-11-04",
        "status": "stored",
        "file_format": "txt",
        "file_size": 12,
    }
    base.update(overrides)
    return base


def test_insert_and_get(tmp_path: Path) -> None:
    repo = DocumentRepository(tmp_path / "documents.sqlite3")
    repo.insert(_record())

    saved = repo.get("DOC-AAAA1111")
    assert saved is not None
    assert saved["title"] == "Guide"
    assert saved["sha256"] == "a" * 64
    assert repo.exists_by_hash("a" * 64) is True
    assert repo.get_by_hash("a" * 64)["document_id"] == "DOC-AAAA1111"


def test_get_unknown_returns_none(tmp_path: Path) -> None:
    repo = DocumentRepository(tmp_path / "documents.sqlite3")
    assert repo.get("DOC-UNKNOWN") is None
    assert repo.get_by_hash("b" * 64) is None
    assert repo.exists_by_hash("b" * 64) is False


def test_duplicate_sha256_rejected_by_sqlite(tmp_path: Path) -> None:
    repo = DocumentRepository(tmp_path / "documents.sqlite3")
    repo.insert(_record())

    with pytest.raises(Exception):
        repo.insert(_record(document_id="DOC-BBBB2222"))


def test_list_documents_by_domain(tmp_path: Path) -> None:
    repo = DocumentRepository(tmp_path / "documents.sqlite3")
    repo.insert(_record())
    repo.insert(
        _record(
            document_id="DOC-CCCC3333",
            sha256="c" * 64,
            domain="education",
            subdomain="exams",
            upload_date="2026-11-05T09:00:00",
        )
    )

    assert len(repo.list_documents()) == 2
    public = repo.list_documents(domain="public_services")
    assert len(public) == 1
    assert public[0]["document_id"] == "DOC-AAAA1111"

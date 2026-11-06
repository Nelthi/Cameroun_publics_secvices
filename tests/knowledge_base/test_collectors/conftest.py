"""Fixtures partagées pour les tests T1."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.knowledge_base.api import create_app
from backend.knowledge_base.collectors import DocumentCollector, DocumentMetadata


@pytest.fixture
def meta() -> DocumentMetadata:
    return DocumentMetadata(
        title="Plaquette CNI",
        institution="DGSN",
        date="2026-11-04",
        domain="public_services",
        subdomain="national_identity_card",
    )


@pytest.fixture
def collector(tmp_path: Path) -> DocumentCollector:
    return DocumentCollector(data_root=tmp_path / "data")


@pytest.fixture
def api_client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(data_root=tmp_path / "data"))


@pytest.fixture
def txt_file(tmp_path: Path) -> Path:
    path = tmp_path / "guide.txt"
    path.write_text("Procédure CNI de test", encoding="utf-8")
    return path


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    path = tmp_path / "doc.pdf"
    path.write_bytes(b"%PDF-1.4\n% contenu minimal de test")
    return path


@pytest.fixture
def docx_file(tmp_path: Path) -> Path:
    path = tmp_path / "note.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document/>")
    return path

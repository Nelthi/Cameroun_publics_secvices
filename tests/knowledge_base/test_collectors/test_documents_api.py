"""Tests API T1 — POST /documents/upload (OK / invalide / vide / doublon / métadonnées)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from fastapi.testclient import TestClient


def _form(**overrides) -> dict[str, str]:
    values = {
        "title": "Plaquette CNI",
        "institution": "DGSN",
        "date": "2025-05-20",
        "domain": "public_services",
        "subdomain": "national_identity_card",
    }
    values.update(overrides)
    return values


def test_health(api_client: TestClient) -> None:
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_and_swagger_available(api_client: TestClient) -> None:
    assert api_client.get("/docs").status_code == 200
    assert api_client.get("/redoc").status_code == 200
    openapi = api_client.get("/openapi.json")
    assert openapi.status_code == 200
    paths = openapi.json()["paths"]
    assert "/documents/upload" in paths
    assert "post" in paths["/documents/upload"]


# --- OK ---


def test_ok_upload_txt_returns_201_and_contract(api_client: TestClient) -> None:
    files = {"file": ("guide.txt", b"Procedure CNI", "text/plain")}

    response = api_client.post("/documents/upload", data=_form(), files=files)

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "stored"
    assert payload["document_id"].startswith("DOC-")
    assert payload["original_filename"] == "guide.txt"
    assert payload["domain"] == "public_services"
    assert payload["institution"] == "DGSN"
    assert payload["stored_path"].startswith(
        "data/raw/public_services/national_identity_card/"
    )
    assert len(payload["sha256"]) == 64
    assert "upload_date" in payload
    assert "is_duplicate" not in payload


def test_ok_upload_docx(api_client: TestClient, tmp_path: Path) -> None:
    docx_path = tmp_path / "note.docx"
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document/>")

    files = {
        "file": (
            "note.docx",
            docx_path.read_bytes(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }

    response = api_client.post("/documents/upload", data=_form(), files=files)

    assert response.status_code == 201
    assert response.json()["original_filename"] == "note.docx"


# --- Doublon ---


def test_duplicate_upload_returns_200(api_client: TestClient) -> None:
    files = {"file": ("guide.txt", b"Meme contenu", "text/plain")}

    first = api_client.post("/documents/upload", data=_form(), files=files)
    second = api_client.post(
        "/documents/upload",
        data=_form(title="Autre titre"),
        files=files,
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["document_id"] == first.json()["document_id"]
    assert second.json()["is_duplicate"] is True


# --- Vide / invalide ---


def test_empty_file_returns_400(api_client: TestClient) -> None:
    files = {"file": ("empty.txt", b"", "text/plain")}

    response = api_client.post("/documents/upload", data=_form(), files=files)

    assert response.status_code == 400
    assert "detail" in response.json()


def test_invalid_pdf_returns_400(api_client: TestClient) -> None:
    files = {"file": ("fake.pdf", b"not-a-pdf", "application/pdf")}

    response = api_client.post("/documents/upload", data=_form(), files=files)

    assert response.status_code == 400
    assert "detail" in response.json()


def test_unsupported_format_returns_415(api_client: TestClient) -> None:
    files = {"file": ("data.csv", b"a,b", "text/csv")}

    response = api_client.post("/documents/upload", data=_form(), files=files)

    assert response.status_code == 415


# --- Métadonnées ---


def test_metadata_invalid_date_returns_400(api_client: TestClient) -> None:
    files = {"file": ("ok.txt", b"ok", "text/plain")}

    response = api_client.post(
        "/documents/upload",
        data=_form(date="20/05/2025"),
        files=files,
    )

    assert response.status_code == 400


def test_metadata_blank_title_returns_400(api_client: TestClient) -> None:
    files = {"file": ("ok.txt", b"ok", "text/plain")}

    response = api_client.post(
        "/documents/upload",
        data=_form(title="   "),
        files=files,
    )

    assert response.status_code == 400


def test_metadata_missing_field_returns_422(api_client: TestClient) -> None:
    files = {"file": ("ok.txt", b"ok", "text/plain")}
    form = _form()
    del form["institution"]

    response = api_client.post("/documents/upload", data=form, files=files)

    assert response.status_code == 422

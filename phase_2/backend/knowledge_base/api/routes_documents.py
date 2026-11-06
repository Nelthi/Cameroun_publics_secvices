"""Routes documents — T1 Ingestion and Storage."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile, status
from fastapi.responses import JSONResponse

from backend.knowledge_base.collectors import (
    DocumentCollector,
    DocumentMetadata,
    InvalidDocumentError,
    MetadataValidationError,
    UnsupportedFormatError,
)

from .schemas import DocumentUploadResponse, ErrorResponse

router = APIRouter(tags=["T1 — Documents"])


def _get_collector(request: Request) -> DocumentCollector:
    data_root = getattr(request.app.state, "data_root", Path("data"))
    return DocumentCollector(data_root=data_root)


@router.post(
    "/documents/upload",
    response_model=DocumentUploadResponse,
    responses={
        200: {
            "model": DocumentUploadResponse,
            "description": "Document déjà présent (doublon SHA-256).",
        },
        201: {
            "model": DocumentUploadResponse,
            "description": "Document stocké avec succès.",
        },
        400: {
            "model": ErrorResponse,
            "description": "Fichier ou métadonnées invalides.",
        },
        415: {
            "model": ErrorResponse,
            "description": "Format de fichier non supporté.",
        },
    },
    summary="Importer un document administratif",
    description=(
        "Reçoit un fichier PDF, DOCX ou TXT avec ses métadonnées, "
        "vérifie l'extension et la signature, calcule le SHA-256, "
        "détecte les doublons, stocke le fichier dans `data/raw/` "
        "et enregistre les informations dans SQLite.\n\n"
        "**T1 n'extrait pas le texte** du document.\n\n"
        "En cas de doublon, aucune nouvelle copie n'est créée : "
        "l'API renvoie l'identifiant du document existant "
        "(`is_duplicate=true`, HTTP 200)."
    ),
)
async def upload_document(
    request: Request,
    file: UploadFile = File(..., description="Fichier PDF, DOCX ou TXT."),
    title: str = Form(..., description="Titre du document.", examples=["Plaquette CNI"]),
    institution: str = Form(..., description="Institution.", examples=["DGSN"]),
    date: str = Form(
        ...,
        description="Date documentaire ISO 8601.",
        examples=["2025-05-20"],
    ),
    domain: str = Form(
        ...,
        description="Domaine métier.",
        examples=["public_services"],
    ),
    subdomain: str = Form(
        ...,
        description="Sous-domaine (chemin de stockage).",
        examples=["national_identity_card"],
    ),
) -> JSONResponse:
    original_filename = file.filename or "upload.bin"
    suffix = Path(original_filename).suffix.lower()

    collector = _get_collector(request)
    metadata = DocumentMetadata(
        title=title,
        institution=institution,
        date=date,
        domain=domain,
        subdomain=subdomain,
    )

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = Path(tmp.name)
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                tmp.write(chunk)

        result = collector.import_document(
            tmp_path,
            metadata,
            original_filename=original_filename,
        )
        payload = result.to_dict()
        http_status = (
            status.HTTP_200_OK if result.is_duplicate else status.HTTP_201_CREATED
        )
        return JSONResponse(content=payload, status_code=http_status)

    except MetadataValidationError as exc:
        return JSONResponse(
            content={"detail": str(exc)},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except UnsupportedFormatError as exc:
        return JSONResponse(
            content={"detail": str(exc)},
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )
    except InvalidDocumentError as exc:
        return JSONResponse(
            content={"detail": str(exc)},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        await file.close()

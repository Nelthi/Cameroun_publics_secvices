"""Schémas Pydantic exposés dans OpenAPI / Swagger (contrat T1)."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentUploadResponse(BaseModel):
    """Réponse de POST /documents/upload — contrat Phase 2 T1."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "DOC-A1B2C3D4",
                "sha256": "9f2c8e1a0b4d7f6e5c3a2b1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1",
                "original_filename": "plaquette.pdf",
                "stored_path": "data/raw/public_services/national_identity_card/DOC-A1B2C3D4.pdf",
                "upload_date": "2026-11-04T10:00:00",
                "domain": "public_services",
                "institution": "DGSN",
                "status": "stored",
                "is_duplicate": False,
            }
        }
    )

    document_id: str = Field(..., description="Identifiant unique du document.")
    sha256: str = Field(..., description="Empreinte SHA-256 du contenu binaire.")
    original_filename: str = Field(..., description="Nom du fichier envoyé.")
    stored_path: str = Field(
        ...,
        description="Chemin de stockage relatif : data/raw/{domain}/{subdomain}/{id}.{ext}",
    )
    upload_date: str = Field(
        ...,
        description="Date/heure d'ingestion au format ISO 8601.",
        examples=["2026-11-04T10:00:00"],
    )
    domain: str = Field(..., description="Domaine métier du document.")
    institution: str = Field(..., description="Institution émettrice.")
    status: Literal["stored"] = Field(
        ...,
        description="Statut T1 après enregistrement.",
    )
    is_duplicate: Optional[bool] = Field(
        default=None,
        description=(
            "Présent et vrai si le contenu SHA-256 existait déjà ; "
            "aucune nouvelle copie n'a été créée."
        ),
    )


class ErrorResponse(BaseModel):
    """Erreur API lisible."""

    detail: str = Field(..., description="Message d'erreur.")

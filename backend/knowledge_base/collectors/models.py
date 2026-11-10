"""Contrats de données T1 (snake_case, dates ISO 8601)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

from .exceptions import MetadataValidationError


@dataclass(frozen=True)
class DocumentMetadata:
    """Métadonnées fournies à l'ingestion.

    Champs Phase 2 : title, institution, date, domain.
    subdomain est requis pour le chemin data/raw/{domain}/{subdomain}/.
    """

    title: str
    institution: str
    date: str
    domain: str
    subdomain: str

    def validate(self) -> None:
        required = {
            "title": self.title,
            "institution": self.institution,
            "date": self.date,
            "domain": self.domain,
            "subdomain": self.subdomain,
        }
        missing = [
            key
            for key, value in required.items()
            if not isinstance(value, str) or not value.strip()
        ]
        if missing:
            raise MetadataValidationError(
                "Champs obligatoires manquants : " + ", ".join(missing)
            )
        self._validate_iso_date(self.date)

    @staticmethod
    def _validate_iso_date(value: str) -> None:
        text = value.strip()
        try:
            date.fromisoformat(text)
            return
        except ValueError:
            pass
        try:
            datetime.fromisoformat(text)
        except ValueError as exc:
            raise MetadataValidationError(
                "date doit respecter le format ISO 8601 "
                "(ex. 2026-11-04 ou 2026-11-04T10:00:00)."
            ) from exc


@dataclass(frozen=True)
class ImportResult:
    """Résultat d'ingestion conforme au contrat Phase 2 T1."""

    document_id: str
    sha256: str
    original_filename: str
    stored_path: str
    upload_date: str
    domain: str
    institution: str
    status: str
    title: Optional[str] = None
    subdomain: Optional[str] = None
    document_date: Optional[str] = None
    is_duplicate: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "document_id": self.document_id,
            "sha256": self.sha256,
            "original_filename": self.original_filename,
            "stored_path": self.stored_path,
            "upload_date": self.upload_date,
            "domain": self.domain,
            "institution": self.institution,
            "status": self.status,
        }
        if self.is_duplicate:
            payload["is_duplicate"] = True
        return payload

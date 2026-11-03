from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DocumentMetadata:
    title: str
    domain: str
    subdomain: str
    institution: str
    document_type: str
    publication_date: Optional[str] = None
    source_url: Optional[str] = None
    reliability: str = "unverified"
    verification_date: Optional[str] = None
    status: str = "active"
    language: str = "fr"

    def validate(self) -> None:
        required = {
            "title": self.title,
            "domain": self.domain,
            "subdomain": self.subdomain,
            "institution": self.institution,
            "document_type": self.document_type,
            "reliability": self.reliability,
            "status": self.status,
            "language": self.language,
        }
        missing = [key for key, value in required.items()
                   if not isinstance(value, str) or not value.strip()]
        if missing:
            from .exceptions import MetadataValidationError
            raise MetadataValidationError(
                "Champs obligatoires manquants : " + ", ".join(missing)
            )

        for field_name, value in (
            ("publication_date", self.publication_date),
            ("verification_date", self.verification_date),
        ):
            if value is not None:
                try:
                    from datetime import date
                    date.fromisoformat(value)
                except (TypeError, ValueError):
                    from .exceptions import MetadataValidationError
                    raise MetadataValidationError(
                        f"{field_name} doit respecter le format YYYY-MM-DD."
                    )

        if self.source_url is not None:
            from urllib.parse import urlparse
            parsed = urlparse(self.source_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                from .exceptions import MetadataValidationError
                raise MetadataValidationError(
                    "source_url doit être une URL HTTP ou HTTPS valide."
                )


@dataclass(frozen=True)
class ImportResult:
    document_id: str
    original_filename: str
    stored_path: str
    file_format: str
    file_size: int
    sha256: str
    imported_at: str
    metadata: DocumentMetadata

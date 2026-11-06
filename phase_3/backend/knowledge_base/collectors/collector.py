"""T1 — Ingestion and Storage : validation, empreinte, stockage, SQLite.

Ce module n'extrait jamais le contenu textuel des documents.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from backend.knowledge_base.database.repository import DocumentRepository

from .exceptions import InvalidDocumentError, UnsupportedFormatError
from .models import DocumentMetadata, ImportResult


class DocumentCollector:
    """Importe PDF, DOCX et TXT, puis enregistre métadonnées et fichier brut."""

    ALLOWED_FORMATS = {".pdf", ".docx", ".txt"}
    DEFAULT_MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MiB
    STATUS_STORED = "stored"

    def __init__(
        self,
        data_root: Union[str, Path] = "data",
        database_path: Optional[Union[str, Path]] = None,
        max_file_size: int = DEFAULT_MAX_FILE_SIZE,
    ) -> None:
        self.data_root = Path(data_root).resolve()
        self.raw_root = self.data_root / "raw"
        self.database_path = (
            Path(database_path).resolve()
            if database_path
            else (self.data_root / "metadata" / "documents.sqlite3")
        )
        if max_file_size <= 0:
            raise ValueError("max_file_size doit être strictement positif.")
        self.max_file_size = max_file_size
        self.repository = DocumentRepository(self.database_path)
        self.raw_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_segment(value: str) -> str:
        """Normalise un segment de chemin (anti path-traversal)."""
        cleaned = value.strip().lower()
        cleaned = re.sub(r"[^a-z0-9_-]+", "_", cleaned)
        cleaned = cleaned.strip("._-")
        if not cleaned or cleaned in {".", ".."}:
            raise InvalidDocumentError("Nom de domaine/sous-domaine invalide.")
        return cleaned[:80]

    @staticmethod
    def _generate_document_id() -> str:
        # Format illustratif Phase 2 : DOC-A1B2C3D4 (8 hex).
        return f"DOC-{uuid.uuid4().hex[:8].upper()}"

    @staticmethod
    def _validate_signature(path: Path, extension: str) -> None:
        try:
            with path.open("rb") as handle:
                header = handle.read(8)
        except OSError as exc:
            raise InvalidDocumentError(f"Lecture impossible : {exc}") from exc

        if extension == ".pdf" and not header.startswith(b"%PDF"):
            raise InvalidDocumentError(
                "Le fichier ne possède pas une signature PDF valide (%PDF)."
            )

        if extension == ".docx":
            if not zipfile.is_zipfile(path):
                raise InvalidDocumentError(
                    "Le fichier DOCX n'est pas une archive ZIP valide."
                )
            try:
                with zipfile.ZipFile(path) as archive:
                    names = set(archive.namelist())
            except zipfile.BadZipFile as exc:
                raise InvalidDocumentError("Archive DOCX corrompue.") from exc
            if "word/document.xml" not in names:
                raise InvalidDocumentError(
                    "L'archive ne contient pas word/document.xml (DOCX invalide)."
                )

        # TXT : pas de signature magique fiable à T1 (encodage traité en T2).

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @classmethod
    def _result_from_record(
        cls,
        record: dict,
        *,
        is_duplicate: bool = False,
    ) -> ImportResult:
        return ImportResult(
            document_id=record["document_id"],
            sha256=record["sha256"],
            original_filename=record["original_filename"],
            stored_path=record["stored_path"],
            upload_date=record["upload_date"],
            domain=record["domain"],
            institution=record["institution"],
            status=record["status"],
            title=record.get("title"),
            subdomain=record.get("subdomain"),
            document_date=record.get("document_date"),
            is_duplicate=is_duplicate,
        )

    def import_document(
        self,
        file_path: Union[str, Path],
        metadata: DocumentMetadata,
        *,
        original_filename: Optional[str] = None,
    ) -> ImportResult:
        """Valide, dédoublonne, stocke et enregistre un document.

        original_filename permet de conserver le nom client lors d'un
        upload via fichier temporaire (API).
        """
        source = Path(file_path).expanduser()
        if not source.exists() or not source.is_file():
            raise InvalidDocumentError(f"Fichier introuvable : {source}")

        display_name = (original_filename or source.name).strip() or source.name
        extension = Path(display_name).suffix.lower()
        if extension not in self.ALLOWED_FORMATS:
            raise UnsupportedFormatError(
                f"Format {extension or '(sans extension)'} non supporté. "
                f"Formats acceptés : {', '.join(sorted(self.ALLOWED_FORMATS))}"
            )

        metadata.validate()

        try:
            size = source.stat().st_size
        except OSError as exc:
            raise InvalidDocumentError(f"Statut fichier illisible : {exc}") from exc

        if size == 0:
            raise InvalidDocumentError("Le fichier est vide.")
        if size > self.max_file_size:
            raise InvalidDocumentError(
                f"Fichier trop volumineux : {size} octets. "
                f"Maximum autorisé : {self.max_file_size} octets."
            )

        self._validate_signature(source, extension)
        file_hash = self._hash_file(source)

        existing = self.repository.get_by_hash(file_hash)
        if existing is not None:
            # Phase 2 : refuser une nouvelle copie, retourner l'ID existant.
            return self._result_from_record(existing, is_duplicate=True)

        domain = self._safe_segment(metadata.domain)
        subdomain = self._safe_segment(metadata.subdomain)
        target_dir = self.raw_root / domain / subdomain
        target_dir.mkdir(parents=True, exist_ok=True)

        document_id = self._generate_document_id()
        # Evite une collision d'ID extrêmement rare.
        while self.repository.get(document_id) is not None:
            document_id = self._generate_document_id()

        stored_filename = f"{document_id}{extension}"
        destination = target_dir / stored_filename
        upload_date = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(
            timespec="seconds"
        )

        # Chemin relatif depuis la racine projet : data/raw/...
        relative_to_data = destination.relative_to(self.data_root).as_posix()
        stored_path = f"data/{relative_to_data}"

        shutil.copy2(source, destination)

        record = {
            "document_id": document_id,
            "sha256": file_hash,
            "original_filename": Path(display_name).name,
            "stored_path": stored_path,
            "upload_date": upload_date,
            "domain": metadata.domain.strip(),
            "subdomain": metadata.subdomain.strip(),
            "institution": metadata.institution.strip(),
            "title": metadata.title.strip(),
            "document_date": metadata.date.strip(),
            "status": self.STATUS_STORED,
            "file_format": extension.lstrip("."),
            "file_size": size,
        }

        try:
            self.repository.insert(record)
        except Exception:
            destination.unlink(missing_ok=True)
            raise

        return self._result_from_record(record, is_duplicate=False)

    def get_document(self, document_id: str) -> Optional[dict]:
        return self.repository.get(document_id)

    def list_documents(self, domain: Optional[str] = None) -> list[dict]:
        return self.repository.list_documents(domain=domain)

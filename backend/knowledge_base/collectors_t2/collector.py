import hashlib
import json
import re
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from .exceptions import (
    DuplicateDocumentError, InvalidDocumentError, UnsupportedFormatError
)
from .models import DocumentMetadata, ImportResult
from .repository import DocumentRepository


class DocumentCollector:
    """
    Imports PDF, DOCX and TXT files, stores them by domain and persists
    their metadata in SQLite. Text extraction is deliberately out of scope.
    """

    ALLOWED_FORMATS = {".pdf", ".docx", ".txt"}
    DEFAULT_MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MiB

    def __init__(
        self,
        data_root: Union[str, Path] = "data",
        database_path: Optional[Union[str, Path]] = None,
        max_file_size: int = DEFAULT_MAX_FILE_SIZE,
    ):
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
        # Prevent path traversal and keep directory names predictable.
        value = value.strip().lower()
        value = re.sub(r"[^a-z0-9_-]+", "_", value)
        value = value.strip("._-")
        if not value or value in {".", ".."}:
            raise ValueError("Nom de domaine/sous-domaine invalide.")
        return value[:80]

    @staticmethod
    def _validate_signature(path: Path, extension: str) -> None:
        try:
            with path.open("rb") as file:
                header = file.read(8)
        except OSError as exc:
            raise InvalidDocumentError(f"Lecture impossible : {exc}") from exc

        if extension == ".pdf" and not header.startswith(b"%PDF-"):
            raise InvalidDocumentError("Le fichier ne possède pas une signature PDF valide.")
        if extension == ".docx":
            # DOCX is an Office Open XML ZIP package.
            if not zipfile.is_zipfile(path):
                raise InvalidDocumentError("Le fichier DOCX n'est pas une archive ZIP valide.")
            try:
                with zipfile.ZipFile(path) as archive:
                    names = set(archive.namelist())
                    if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                        raise InvalidDocumentError("L'archive ne contient pas un document DOCX valide.")
            except zipfile.BadZipFile as exc:
                raise InvalidDocumentError("Archive DOCX corrompue.") from exc
        if extension == ".txt":
            try:
                path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise InvalidDocumentError(
                    "Le fichier TXT doit être encodé en UTF-8."
                ) from exc

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def import_document(
        self,
        file_path: Union[str, Path],
        metadata: DocumentMetadata,
        *,
        allow_duplicate: bool = False,
    ) -> ImportResult:
        source = Path(file_path).expanduser()
        if not source.exists() or not source.is_file():
            raise InvalidDocumentError(f"Fichier introuvable : {source}")
        extension = source.suffix.lower()
        if extension not in self.ALLOWED_FORMATS:
            raise UnsupportedFormatError(
                f"Format {extension or '(sans extension)'} non supporté. "
                f"Formats acceptés : {', '.join(sorted(self.ALLOWED_FORMATS))}"
            )

        metadata.validate()
        size = source.stat().st_size
        if size == 0:
            raise InvalidDocumentError("Le fichier est vide.")
        if size > self.max_file_size:
            raise InvalidDocumentError(
                f"Fichier trop volumineux : {size} octets. "
                f"Maximum autorisé : {self.max_file_size} octets."
            )

        self._validate_signature(source, extension)
        file_hash = self._hash_file(source)

        if not allow_duplicate and self.repository.exists_by_hash(file_hash):
            raise DuplicateDocumentError(
                "Ce contenu existe déjà dans la Knowledge Base (SHA-256 identique)."
            )

        domain = self._safe_segment(metadata.domain)
        subdomain = self._safe_segment(metadata.subdomain)
        target_dir = self.raw_root / domain / subdomain
        target_dir.mkdir(parents=True, exist_ok=True)

        document_id = f"DOC-{uuid.uuid4().hex[:12].upper()}"
        stored_filename = f"{document_id}{extension}"
        destination = target_dir / stored_filename
        imported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        # Copy first; if database insertion fails, remove the copied file.
        shutil.copy2(source, destination)
        relative_path = destination.relative_to(self.data_root).as_posix()

        record = {
            "document_id": document_id,
            "original_filename": source.name,
            "stored_filename": stored_filename,
            "stored_path": relative_path,
            "file_format": extension.lstrip("."),
            "file_size": size,
            "sha256": file_hash,
            "imported_at": imported_at,
            "metadata": {
                "title": metadata.title,
                "domain": metadata.domain,
                "subdomain": metadata.subdomain,
                "institution": metadata.institution,
                "document_type": metadata.document_type,
                "publication_date": metadata.publication_date,
                "source_url": metadata.source_url,
                "reliability": metadata.reliability,
                "verification_date": metadata.verification_date,
                "status": metadata.status,
                "language": metadata.language,
            },
        }

        try:
            self.repository.insert(record)
        except Exception:
            destination.unlink(missing_ok=True)
            raise

        return ImportResult(
            document_id=document_id,
            original_filename=source.name,
            stored_path=relative_path,
            file_format=extension.lstrip("."),
            file_size=size,
            sha256=file_hash,
            imported_at=imported_at,
            metadata=metadata,
        )

    def get_document(self, document_id: str):
        return self.repository.get(document_id)

    def list_documents(self, domain: Optional[str] = None):
        return self.repository.list_documents(domain=domain)

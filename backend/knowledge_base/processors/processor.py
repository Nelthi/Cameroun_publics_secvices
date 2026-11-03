import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from docx import Document as WordDocument
from pypdf import PdfReader

from ..collectors.repository import DocumentRepository
from .exceptions import (
    DocumentNotFoundError,
    DocumentProcessingError,
    SourceFileError,
    TextExtractionError,
)
from .models import ProcessingResult, TextSegment


class DocumentProcessor:
    """Extrait et normalise le texte des documents importés par le Collector.

    Les originaux restent intacts dans data/raw. Le résultat structuré est
    enregistré en JSON dans data/processed.
    """

    SUPPORTED_FORMATS = {"pdf", "docx", "txt"}

    def __init__(self, data_root="data", database_path=None):
        self.data_root = Path(data_root).resolve()
        self.raw_root = (self.data_root / "raw").resolve()
        self.processed_root = self.data_root / "processed"
        db_path = Path(database_path).resolve() if database_path else (
            self.data_root / "metadata" / "documents.sqlite3"
        )
        self.repository = DocumentRepository(db_path)
        self.processed_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_segment(value: str) -> str:
        value = re.sub(r"[^a-z0-9_-]+", "_", str(value).strip().lower())
        value = value.strip("._-")
        if not value or value in {".", ".."}:
            raise SourceFileError("Domaine ou sous-domaine invalide dans les métadonnées.")
        return value[:80]

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalisation prudente : conserve les paragraphes et la ponctuation."""
        text = unicodedata.normalize("NFC", text or "")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\u00a0", " ").replace("\u200b", "")
        lines = [re.sub(r"[\t ]+", " ", line).strip() for line in text.split("\n")]
        normalized = "\n".join(lines)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    def _get_source_path(self, record: Dict) -> Path:
        relative_path = Path(record["stored_path"])
        if relative_path.is_absolute():
            raise SourceFileError("Le chemin du document brut doit être relatif.")
        source = (self.data_root / relative_path).resolve()
        try:
            source.relative_to(self.raw_root)
        except ValueError as exc:
            raise SourceFileError("Le chemin enregistré sort du dossier data/raw.") from exc
        if not source.is_file():
            raise SourceFileError(f"Fichier brut introuvable : {source}")
        actual_format = source.suffix.lower().lstrip(".")
        if actual_format != record["file_format"].lower():
            raise SourceFileError("L'extension du fichier ne correspond pas au registre.")
        return source

    def _extract_txt(self, source: Path) -> Tuple[List[TextSegment], List[str]]:
        try:
            text = source.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            raise TextExtractionError("Le fichier TXT n'est pas encodé en UTF-8.") from exc
        cleaned = self.normalize_text(text)
        return ([TextSegment("SEG-0001", cleaned)] if cleaned else []), []

    def _extract_pdf(self, source: Path) -> Tuple[List[TextSegment], List[str]]:
        warnings: List[str] = []
        segments: List[TextSegment] = []
        try:
            reader = PdfReader(str(source), strict=False)
            if reader.is_encrypted:
                try:
                    result = reader.decrypt("")
                except Exception:
                    result = 0
                if not result:
                    raise TextExtractionError(
                        "Le PDF est protégé par mot de passe ; extraction impossible."
                    )
            for page_index, page in enumerate(reader.pages, start=1):
                try:
                    raw_text = page.extract_text() or ""
                except Exception as exc:
                    warnings.append(f"Page {page_index} : extraction impossible ({exc}).")
                    raw_text = ""
                cleaned = self.normalize_text(raw_text)
                if cleaned:
                    segments.append(TextSegment(
                        segment_id=f"SEG-{page_index:04d}",
                        text=cleaned,
                        page_number=page_index,
                    ))
                else:
                    warnings.append(
                        f"Page {page_index} : aucun texte détecté (PDF scanné ou page vide possible)."
                    )
        except TextExtractionError:
            raise
        except Exception as exc:
            raise TextExtractionError(f"Lecture du PDF impossible : {exc}") from exc
        if not segments:
            warnings.append("Aucun texte exploitable : une étape OCR sera nécessaire si le PDF est scanné.")
        return segments, warnings

    def _extract_docx(self, source: Path) -> Tuple[List[TextSegment], List[str]]:
        try:
            document = WordDocument(str(source))
        except Exception as exc:
            raise TextExtractionError(f"Lecture du DOCX impossible : {exc}") from exc

        parts: List[str] = []
        for paragraph in document.paragraphs:
            value = self.normalize_text(paragraph.text)
            if value:
                parts.append(value)

        # Les tableaux contiennent souvent des listes de pièces et des frais.
        for table in document.tables:
            for row in table.rows:
                cells = [self.normalize_text(cell.text) for cell in row.cells]
                cells = [cell for cell in cells if cell]
                if cells:
                    parts.append(" | ".join(cells))

        text = self.normalize_text("\n".join(parts))
        return ([TextSegment("SEG-0001", text)] if text else []), []

    def process_document(self, document_id: str) -> ProcessingResult:
        record = self.repository.get(document_id)
        if record is None:
            raise DocumentNotFoundError(f"Document inconnu : {document_id}")

        file_format = record["file_format"].lower()
        if file_format not in self.SUPPORTED_FORMATS:
            raise DocumentProcessingError(f"Format non supporté : {file_format}")
        source = self._get_source_path(record)

        extractors = {
            "pdf": self._extract_pdf,
            "docx": self._extract_docx,
            "txt": self._extract_txt,
        }
        segments, warnings = extractors[file_format](source)
        full_text = "\n\n".join(segment.text for segment in segments)
        status = "processed" if full_text else "needs_ocr_or_review"
        processed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        metadata = record["metadata"]
        domain = self._safe_segment(metadata["domain"])
        subdomain = self._safe_segment(metadata["subdomain"])
        output_dir = self.processed_root / domain / subdomain
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{document_id}.json"
        relative_output = output_file.relative_to(self.data_root).as_posix()

        payload = {
            "document_id": document_id,
            "source": {
                "original_filename": record["original_filename"],
                "stored_path": record["stored_path"],
                "file_format": file_format,
                "sha256": record["sha256"],
            },
            "metadata": metadata,
            "content": {
                "text": full_text,
                "segments": [segment.to_dict() for segment in segments],
            },
            "processing": {
                "processor_version": "1.0.0",
                "processed_at": processed_at,
                "status": status,
                "character_count": len(full_text),
                "segment_count": len(segments),
                "warnings": warnings,
            },
        }

        # Écriture atomique : évite de laisser un JSON partiel si interruption.
        temporary_file = output_file.with_suffix(".json.tmp")
        try:
            temporary_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temporary_file.replace(output_file)
        except OSError as exc:
            temporary_file.unlink(missing_ok=True)
            raise DocumentProcessingError(f"Écriture du résultat impossible : {exc}") from exc

        return ProcessingResult(
            document_id=document_id,
            status=status,
            output_path=relative_output,
            character_count=len(full_text),
            segment_count=len(segments),
            warnings=warnings,
        )

    def process_all(self, domain=None) -> List[ProcessingResult]:
        results = []
        for record in self.repository.list_documents(domain=domain):
            results.append(self.process_document(record["document_id"]))
        return results

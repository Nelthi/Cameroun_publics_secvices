import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .exceptions import (
    InvalidChunkingConfigError,
    InvalidProcessedDocumentError,
    ProcessedDocumentNotFoundError,
)
from .models import ChunkingResult, TextChunk


class TextChunker:
    """Découpe le texte normalisé en chunks en préservant sa provenance.

    Le découpage est réalisé séparément pour chaque segment source. Ainsi, un
    segment PDF conserve son numéro de page et un chunk ne mélange pas deux pages.
    """

    def __init__(self, data_root="data", chunk_size=1000, overlap=150):
        if not isinstance(chunk_size, int) or chunk_size < 100:
            raise InvalidChunkingConfigError("chunk_size doit être un entier >= 100.")
        if not isinstance(overlap, int) or overlap < 0:
            raise InvalidChunkingConfigError("overlap doit être un entier >= 0.")
        if overlap >= chunk_size:
            raise InvalidChunkingConfigError("overlap doit être inférieur à chunk_size.")

        self.data_root = Path(data_root).resolve()
        self.processed_root = (self.data_root / "processed").resolve()
        self.chunks_root = self.data_root / "chunks"
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.chunks_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_segment(value: str) -> str:
        value = re.sub(r"[^a-z0-9_-]+", "_", str(value).strip().lower())
        value = value.strip("._-")
        if not value or value in {".", ".."}:
            raise InvalidProcessedDocumentError("Domaine/sous-domaine invalide.")
        return value[:80]

    def _processed_file(self, document_id: str) -> Path:
        if not re.fullmatch(r"DOC-[A-Fa-f0-9]{12}", document_id or ""):
            raise ProcessedDocumentNotFoundError("Identifiant de document invalide.")
        matches = list(self.processed_root.rglob(f"{document_id}.json"))
        if not matches:
            raise ProcessedDocumentNotFoundError(
                f"Résultat du Document Processor introuvable pour {document_id}. "
                "Exécute d'abord le Document Processor."
            )
        if len(matches) > 1:
            raise InvalidProcessedDocumentError(
                f"Plusieurs fichiers traités portent l'identifiant {document_id}."
            )
        return matches[0]

    def _make_text_chunks(self, text: str, document_id: str,
                          page_number: Optional[int], start_index: int) -> List[TextChunk]:
        """Découpe avec fenêtres chevauchantes et frontières de mots/paragraphes."""
        text = (text or "").strip()
        if not text:
            return []

        raw_chunks: List[str] = []
        start = 0
        text_length = len(text)
        while start < text_length:
            hard_end = min(start + self.chunk_size, text_length)
            end = hard_end

            if hard_end < text_length:
                # Cherche une frontière de paragraphe, puis de mot, près de la
                # limite. On évite ainsi de couper trop tôt les chunks.
                search_floor = start + int(self.chunk_size * 0.60)
                paragraph_boundary = text.rfind("\n\n", search_floor, hard_end)
                word_boundary = text.rfind(" ", search_floor, hard_end)
                boundary = max(paragraph_boundary, word_boundary)
                if boundary > start:
                    end = boundary

            chunk_text = text[start:end].strip()
            if chunk_text:
                raw_chunks.append(chunk_text)

            if end >= text_length:
                break

            # Le prochain chunk reprend avant la fin du précédent pour
            # conserver le contexte. On évite de démarrer au milieu d'un mot.
            next_start = max(start + 1, end - self.overlap)
            while next_start < end and not text[next_start - 1].isspace():
                next_start += 1
            if next_start <= start:
                next_start = end
            start = next_start

        chunks: List[TextChunk] = []
        for offset, chunk_text in enumerate(raw_chunks):
            chunks.append(TextChunk(
                chunk_id=f"CHK-{document_id[4:]}-{start_index + offset:04d}",
                document_id=document_id,
                text=chunk_text,
                chunk_index=start_index + offset,
                page_number=page_number,
            ))
        return chunks

    def chunk_document(self, document_id: str) -> ChunkingResult:
        source_file = self._processed_file(document_id)
        try:
            payload = json.loads(source_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InvalidProcessedDocumentError(
                f"Impossible de lire le JSON traité : {exc}"
            ) from exc

        if payload.get("document_id") != document_id:
            raise InvalidProcessedDocumentError("L'identifiant du JSON ne correspond pas au fichier.")
        processing = payload.get("processing", {})
        if processing.get("status") != "processed":
            raise InvalidProcessedDocumentError(
                "Le document n'a pas un statut 'processed' ; vérifie le résultat du Processor."
            )
        segments = payload.get("content", {}).get("segments")
        if not isinstance(segments, list) or not segments:
            raise InvalidProcessedDocumentError("Aucun segment de texte disponible.")

        metadata = payload.get("metadata", {})
        domain = self._safe_segment(metadata.get("domain", ""))
        subdomain = self._safe_segment(metadata.get("subdomain", ""))

        chunks: List[TextChunk] = []
        for segment in segments:
            if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
                raise InvalidProcessedDocumentError("Un segment source est mal formé.")
            page_number = segment.get("page_number")
            if page_number is not None and (not isinstance(page_number, int) or page_number < 1):
                raise InvalidProcessedDocumentError("Numéro de page invalide dans un segment.")
            chunks.extend(self._make_text_chunks(
                segment["text"], document_id, page_number, len(chunks) + 1
            ))

        status = "chunked" if chunks else "empty"
        output_dir = self.chunks_root / domain / subdomain
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{document_id}.json"
        relative_output = output_file.relative_to(self.data_root).as_posix()
        result_payload: Dict = {
            "document_id": document_id,
            "source": payload.get("source", {}),
            "metadata": metadata,
            "chunking": {
                "chunker_version": "1.0.0",
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "status": status,
                "chunk_size": self.chunk_size,
                "overlap": self.overlap,
                "chunk_count": len(chunks),
                "strategy": "paragraph_aware_per_source_segment",
            },
            "chunks": [chunk.to_dict() for chunk in chunks],
        }

        temporary_file = output_file.with_suffix(".json.tmp")
        try:
            temporary_file.write_text(
                json.dumps(result_payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temporary_file.replace(output_file)
        except OSError as exc:
            temporary_file.unlink(missing_ok=True)
            raise InvalidProcessedDocumentError(f"Écriture des chunks impossible : {exc}") from exc

        return ChunkingResult(
            document_id=document_id,
            status=status,
            output_path=relative_output,
            chunk_count=len(chunks),
            chunk_size=self.chunk_size,
            overlap=self.overlap,
        )

    def chunk_all(self, domain: Optional[str] = None) -> List[ChunkingResult]:
        if not self.processed_root.exists():
            return []
        results = []
        for path in sorted(self.processed_root.rglob("DOC-*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                metadata = payload.get("metadata", {})
                if domain and str(metadata.get("domain", "")).lower() != domain.lower():
                    continue
                results.append(self.chunk_document(payload.get("document_id", "")))
            except (OSError, json.JSONDecodeError) as exc:
                raise InvalidProcessedDocumentError(f"Fichier traité illisible {path}: {exc}") from exc
        return results

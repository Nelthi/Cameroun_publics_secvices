from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class TextSegment:
    """Unité de texte extraite ; page_number est renseigné pour les PDF."""
    segment_id: str
    text: str
    page_number: int | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "page_number": self.page_number,
            "text": self.text,
        }


@dataclass(frozen=True)
class ProcessingResult:
    document_id: str
    status: str
    output_path: str
    character_count: int
    segment_count: int
    warnings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "status": self.status,
            "output_path": self.output_path,
            "character_count": self.character_count,
            "segment_count": self.segment_count,
            "warnings": list(self.warnings),
        }

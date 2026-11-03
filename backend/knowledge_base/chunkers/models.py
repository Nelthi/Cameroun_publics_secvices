from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class TextChunk:
    chunk_id: str
    document_id: str
    text: str
    chunk_index: int
    page_number: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "text": self.text,
            "character_count": len(self.text),
        }


@dataclass(frozen=True)
class ChunkingResult:
    document_id: str
    status: str
    output_path: str
    chunk_count: int
    chunk_size: int
    overlap: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "status": self.status,
            "output_path": self.output_path,
            "chunk_count": self.chunk_count,
            "chunk_size": self.chunk_size,
            "overlap": self.overlap,
        }

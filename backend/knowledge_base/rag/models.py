from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SourceReference:
    label: str
    document_id: str
    chunk_id: str
    title: str
    institution: str
    page_number: Optional[int]
    source_url: Optional[str]
    score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "title": self.title,
            "institution": self.institution,
            "page_number": self.page_number,
            "source_url": self.source_url,
            "score": self.score,
        }


@dataclass(frozen=True)
class RagResponse:
    question: str
    answer: str
    abstained: bool
    reason: Optional[str]
    sources: List[SourceReference]
    retrieved_count: int
    model: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "abstained": self.abstained,
            "reason": self.reason,
            "retrieved_count": self.retrieved_count,
            "model": self.model,
            "sources": [source.to_dict() for source in self.sources],
        }

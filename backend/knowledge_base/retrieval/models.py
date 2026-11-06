from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class RetrievedChunk:
    rank: int
    score: float
    document_id: str
    chunk_id: str
    text: str
    page_number: Optional[int]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "score": self.score,
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "text": self.text,
            "page_number": self.page_number,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class RetrievalResponse:
    query: str
    results: List[RetrievedChunk]
    context: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "result_count": len(self.results),
            "results": [item.to_dict() for item in self.results],
            "context": self.context,
        }

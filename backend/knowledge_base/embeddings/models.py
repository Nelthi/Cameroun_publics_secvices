from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class EmbeddingResult:
    document_id: str
    status: str
    output_dir: str
    embedding_count: int
    embedding_dimension: int
    model_name: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "status": self.status,
            "output_dir": self.output_dir,
            "embedding_count": self.embedding_count,
            "embedding_dimension": self.embedding_dimension,
            "model_name": self.model_name,
        }

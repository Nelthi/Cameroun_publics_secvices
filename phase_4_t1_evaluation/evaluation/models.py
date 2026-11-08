"""Contrats de données Phase 4 T1 (snake_case).

- Jeu de questions (entrée manuelle)
- Réponse provisoire POST /ask
- Rapport d'évaluation officiel (champs imposés)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class SourceRef:
    """Référence documentaire attendue ou obtenue."""

    document_id: str
    chunk_id: Optional[str] = None
    source_page: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"document_id": self.document_id}
        if self.chunk_id is not None:
            payload["chunk_id"] = self.chunk_id
        if self.source_page is not None:
            payload["source_page"] = self.source_page
        return payload


@dataclass(frozen=True)
class ExpectedResult:
    """Résultat attendu pour une question de test."""

    refused: bool
    sources: tuple[SourceRef, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "refused": self.refused,
            "sources": [source.to_dict() for source in self.sources],
        }


@dataclass(frozen=True)
class QuestionCase:
    """Cas de test manuel."""

    question_id: str
    question: str
    language: str
    expected: ExpectedResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question": self.question,
            "language": self.language,
            "expected": self.expected.to_dict(),
        }


@dataclass(frozen=True)
class AskResponse:
    """Réponse provisoire de POST /ask (alignement ultérieur possible)."""

    request_id: str
    answer: str
    refused: bool
    sources: tuple[SourceRef, ...]
    duration_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "answer": self.answer,
            "refused": self.refused,
            "sources": [source.to_dict() for source in self.sources],
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True)
class EvalMetrics:
    """Métriques obligatoires du rapport Phase 4."""

    source_hit_rate: float
    correct_refusal_rate: float
    avg_duration_ms: float

    def to_dict(self) -> dict[str, float]:
        return {
            "source_hit_rate": self.source_hit_rate,
            "correct_refusal_rate": self.correct_refusal_rate,
            "avg_duration_ms": self.avg_duration_ms,
        }


@dataclass(frozen=True)
class FailureRecord:
    """Échec individuel — contrat Phase 4."""

    question_id: str
    expected: dict[str, Any]
    got: dict[str, Any]
    request_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "expected": self.expected,
            "got": self.got,
            "request_id": self.request_id,
        }


@dataclass(frozen=True)
class EvalReport:
    """Rapport d'évaluation — champs obligatoires uniquement."""

    run_id: str
    n_questions: int
    metrics: EvalMetrics
    failures: tuple[FailureRecord, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "n_questions": self.n_questions,
            "metrics": self.metrics.to_dict(),
            "failures": [failure.to_dict() for failure in self.failures],
        }

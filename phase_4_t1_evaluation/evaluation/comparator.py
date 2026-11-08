"""Comparaison expected vs réponse /ask (contrat provisoire).

Règles de source (provisoires, documentées) :
- Un « source hit » est vrai si au moins un document_id attendu apparaît
  dans les sources obtenues.
- chunk_id / source_page sont informatifs ; le match minimal porte sur
  document_id (stable même si le chunking Phase 2 évolue).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import AskResponse, ExpectedResult, FailureRecord, QuestionCase, SourceRef


@dataclass(frozen=True)
class ComparisonResult:
    """Résultat de comparaison pour une question."""

    question_id: str
    request_id: str
    passed: bool
    source_hit: Optional[bool]
    """True/False si la question est éligible au calcul source_hit_rate, sinon None."""

    refusal_correct: Optional[bool]
    """True/False si refusal attendu, sinon None."""

    duration_ms: Optional[float]
    """Durée si l'appel a produit une AskResponse valide, sinon None."""

    failure: Optional[FailureRecord]


def _source_ids(sources: tuple[SourceRef, ...]) -> set[str]:
    return {source.document_id for source in sources}


def has_source_hit(expected: ExpectedResult, got: AskResponse) -> bool:
    """Au moins un document_id attendu est présent dans la réponse."""
    expected_ids = _source_ids(expected.sources)
    got_ids = _source_ids(got.sources)
    if not expected_ids:
        return False
    return bool(expected_ids & got_ids)


def compare_case(case: QuestionCase, got: AskResponse) -> ComparisonResult:
    """Compare un cas de test à une réponse /ask réussie.

    Ne traite pas les erreurs réseau : celles-ci n'entrent pas ici
    (pas de AskResponse) et ne comptent pas comme refus correct.
    """
    expected = case.expected
    source_hit: Optional[bool] = None
    refusal_correct: Optional[bool] = None

    if expected.refused:
        # Refus correct = drapeau refused + aucune source renvoyée.
        refusal_correct = got.refused is True and len(got.sources) == 0
        passed = refusal_correct
    else:
        # Question non-refus : on attend refused=false + hit source si sources prévues
        if expected.sources:
            source_hit = has_source_hit(expected, got)
            passed = (got.refused is False) and source_hit
        else:
            passed = got.refused is False

    failure = None
    if not passed:
        failure = FailureRecord(
            question_id=case.question_id,
            expected=expected.to_dict(),
            got=got.to_dict(),
            request_id=got.request_id,
        )

    return ComparisonResult(
        question_id=case.question_id,
        request_id=got.request_id,
        passed=passed,
        source_hit=source_hit,
        refusal_correct=refusal_correct,
        duration_ms=got.duration_ms,
        failure=failure,
    )

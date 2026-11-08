"""Calcul des métriques Phase 4 T1.

Dénominateurs (fixés) :

source_hit_rate
  numérateur   = nombre de questions avec source_hit == True
  dénominateur = nombre de questions éligibles (expected.refused == False
                 ET expected.sources non vide)
  si dénominateur == 0 → 0.0

correct_refusal_rate
  numérateur   = nombre de questions avec refusal_correct == True
  dénominateur = nombre de questions avec expected.refused == True
                 (donc refusal_correct is not None)
  Les erreurs réseau ne créent pas de ComparisonResult refusal :
  elles n'entrent pas dans ce dénominateur.
  si dénominateur == 0 → 0.0

avg_duration_ms
  numérateur   = somme des duration_ms des ComparisonResult avec duration_ms
  dénominateur = nombre de ces résultats
  si dénominateur == 0 → 0.0
"""

from __future__ import annotations

from .comparator import ComparisonResult
from .models import EvalMetrics, EvalReport, FailureRecord


def compute_metrics(results: list[ComparisonResult]) -> EvalMetrics:
    """Agrège les comparaisons en métriques officielles."""
    source_hits = [item for item in results if item.source_hit is not None]
    source_hit_rate = (
        sum(1 for item in source_hits if item.source_hit) / len(source_hits)
        if source_hits
        else 0.0
    )

    refusals = [item for item in results if item.refusal_correct is not None]
    correct_refusal_rate = (
        sum(1 for item in refusals if item.refusal_correct) / len(refusals)
        if refusals
        else 0.0
    )

    durations = [
        item.duration_ms for item in results if item.duration_ms is not None
    ]
    avg_duration_ms = sum(durations) / len(durations) if durations else 0.0

    return EvalMetrics(
        source_hit_rate=source_hit_rate,
        correct_refusal_rate=correct_refusal_rate,
        avg_duration_ms=avg_duration_ms,
    )


def build_report(
    run_id: str,
    n_questions: int,
    results: list[ComparisonResult],
    extra_failures: list[FailureRecord] | None = None,
) -> EvalReport:
    """Construit le rapport Phase 4 (échec comparaison + échecs d'exécution)."""
    failures: list[FailureRecord] = [
        item.failure for item in results if item.failure is not None
    ]
    if extra_failures:
        failures.extend(extra_failures)

    return EvalReport(
        run_id=run_id,
        n_questions=n_questions,
        metrics=compute_metrics(results),
        failures=tuple(failures),
    )

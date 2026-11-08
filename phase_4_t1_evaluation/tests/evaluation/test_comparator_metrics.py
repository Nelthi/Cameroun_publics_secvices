"""Tests Étape 4 — comparaison et métriques."""

from __future__ import annotations

from evaluation.comparator import compare_case, has_source_hit
from evaluation.metrics import build_report, compute_metrics
from evaluation.models import (
    AskResponse,
    ExpectedResult,
    QuestionCase,
    SourceRef,
)


def _case(
    question_id: str,
    *,
    refused: bool,
    sources: tuple[SourceRef, ...] = (),
) -> QuestionCase:
    return QuestionCase(
        question_id=question_id,
        question="question fictive",
        language="fr",
        expected=ExpectedResult(refused=refused, sources=sources),
    )


def _got(
    *,
    refused: bool,
    sources: tuple[SourceRef, ...] = (),
    duration_ms: float = 10.0,
    request_id: str = "REQ-1",
) -> AskResponse:
    return AskResponse(
        request_id=request_id,
        answer="",
        refused=refused,
        sources=sources,
        duration_ms=duration_ms,
    )


def test_source_hit_matches_document_id() -> None:
    expected = ExpectedResult(
        refused=False,
        sources=(SourceRef(document_id="DOC-A"),),
    )
    got = _got(refused=False, sources=(SourceRef(document_id="DOC-A", chunk_id="X"),))
    assert has_source_hit(expected, got) is True


def test_source_hit_false_when_no_overlap() -> None:
    expected = ExpectedResult(
        refused=False,
        sources=(SourceRef(document_id="DOC-A"),),
    )
    got = _got(refused=False, sources=(SourceRef(document_id="DOC-B"),))
    assert has_source_hit(expected, got) is False


def test_compare_non_refusal_pass() -> None:
    case = _case("Q1", refused=False, sources=(SourceRef(document_id="DOC-A"),))
    result = compare_case(case, _got(refused=False, sources=(SourceRef(document_id="DOC-A"),)))
    assert result.passed is True
    assert result.source_hit is True
    assert result.refusal_correct is None
    assert result.failure is None


def test_compare_non_refusal_fail_builds_failure_record() -> None:
    case = _case("Q1", refused=False, sources=(SourceRef(document_id="DOC-A"),))
    result = compare_case(case, _got(refused=False, sources=(SourceRef(document_id="DOC-B"),)))
    assert result.passed is False
    assert result.failure is not None
    assert result.failure.question_id == "Q1"
    assert set(result.failure.to_dict()) == {
        "question_id",
        "expected",
        "got",
        "request_id",
    }


def test_compare_correct_refusal() -> None:
    case = _case("Q2", refused=True)
    result = compare_case(case, _got(refused=True, sources=()))
    assert result.passed is True
    assert result.refusal_correct is True
    assert result.source_hit is None


def test_compare_incorrect_refusal_when_sources_present() -> None:
    case = _case("Q2", refused=True)
    result = compare_case(
        case,
        _got(refused=True, sources=(SourceRef(document_id="DOC-A"),)),
    )
    assert result.passed is False
    assert result.refusal_correct is False


def test_metrics_denominators() -> None:
    results = [
        compare_case(
            _case("Q1", refused=False, sources=(SourceRef(document_id="DOC-A"),)),
            _got(refused=False, sources=(SourceRef(document_id="DOC-A"),), duration_ms=10),
        ),
        compare_case(
            _case("Q2", refused=False, sources=(SourceRef(document_id="DOC-A"),)),
            _got(refused=False, sources=(SourceRef(document_id="DOC-B"),), duration_ms=30),
        ),
        compare_case(
            _case("Q3", refused=True),
            _got(refused=True, duration_ms=20),
        ),
        compare_case(
            _case("Q4", refused=True),
            _got(refused=False, duration_ms=40),
        ),
    ]

    metrics = compute_metrics(results)
    # source: 1 hit / 2 eligible
    assert metrics.source_hit_rate == 0.5
    # refusal: 1 correct / 2 expected refusals
    assert metrics.correct_refusal_rate == 0.5
    # avg duration: (10+30+20+40)/4
    assert metrics.avg_duration_ms == 25.0


def test_metrics_zero_when_empty() -> None:
    metrics = compute_metrics([])
    assert metrics.source_hit_rate == 0.0
    assert metrics.correct_refusal_rate == 0.0
    assert metrics.avg_duration_ms == 0.0


def test_build_report_contract() -> None:
    results = [
        compare_case(
            _case("Q1", refused=False, sources=(SourceRef(document_id="DOC-A"),)),
            _got(refused=False, sources=(SourceRef(document_id="DOC-B"),)),
        )
    ]
    report = build_report("run-1", n_questions=1, results=results)
    payload = report.to_dict()
    assert payload["run_id"] == "run-1"
    assert payload["n_questions"] == 1
    assert len(payload["failures"]) == 1

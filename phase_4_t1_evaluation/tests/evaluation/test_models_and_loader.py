"""Tests Étape 1 — modèles + validation questions.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.exceptions import QuestionsValidationError
from evaluation.models import (
    AskResponse,
    EvalMetrics,
    EvalReport,
    ExpectedResult,
    FailureRecord,
    QuestionCase,
    SourceRef,
)
from evaluation.questions_loader import load_questions_file, parse_questions_payload


def _valid_payload() -> dict:
    return {
        "questions": [
            {
                "question_id": "Q001",
                "question": "Comment obtenir une CNI fictive ?",
                "language": "fr",
                "expected": {
                    "refused": False,
                    "sources": [
                        {
                            "document_id": "DOC-AAAA1111",
                            "chunk_id": "DOC-AAAA1111-C001",
                            "source_page": 1,
                        }
                    ],
                },
            },
            {
                "question_id": "Q002",
                "question": "Donne-moi une recette de cuisine",
                "language": "fr",
                "expected": {"refused": True, "sources": []},
            },
        ]
    }


def test_parse_valid_questions_payload() -> None:
    cases = parse_questions_payload(_valid_payload())
    assert len(cases) == 2
    assert cases[0].question_id == "Q001"
    assert cases[0].expected.refused is False
    assert cases[0].expected.sources[0].document_id == "DOC-AAAA1111"
    assert cases[1].expected.refused is True


def test_eval_report_contract_keys_only() -> None:
    report = EvalReport(
        run_id="run-test",
        n_questions=2,
        metrics=EvalMetrics(
            source_hit_rate=1.0,
            correct_refusal_rate=1.0,
            avg_duration_ms=10.0,
        ),
        failures=(
            FailureRecord(
                question_id="Q001",
                expected={"refused": False},
                got={"refused": True},
                request_id="REQ-1",
            ),
        ),
    )
    payload = report.to_dict()
    assert set(payload.keys()) == {
        "run_id",
        "n_questions",
        "metrics",
        "failures",
    }
    assert set(payload["metrics"].keys()) == {
        "source_hit_rate",
        "correct_refusal_rate",
        "avg_duration_ms",
    }
    assert set(payload["failures"][0].keys()) == {
        "question_id",
        "expected",
        "got",
        "request_id",
    }


def test_ask_response_to_dict() -> None:
    response = AskResponse(
        request_id="REQ-1",
        answer="Réponse fictive",
        refused=False,
        sources=(SourceRef(document_id="DOC-1"),),
        duration_ms=42.0,
    )
    assert response.to_dict()["duration_ms"] == 42.0


def test_reject_missing_questions_key() -> None:
    with pytest.raises(QuestionsValidationError):
        parse_questions_payload({})


def test_reject_empty_questions_list() -> None:
    with pytest.raises(QuestionsValidationError):
        parse_questions_payload({"questions": []})


def test_reject_duplicate_question_id() -> None:
    payload = _valid_payload()
    payload["questions"][1]["question_id"] = "Q001"
    with pytest.raises(QuestionsValidationError):
        parse_questions_payload(payload)


def test_reject_refused_with_sources() -> None:
    payload = _valid_payload()
    payload["questions"][1]["expected"]["sources"] = [
        {"document_id": "DOC-X"}
    ]
    with pytest.raises(QuestionsValidationError):
        parse_questions_payload(payload)


def test_reject_unexpected_root_field() -> None:
    payload = _valid_payload()
    payload["extra"] = True
    with pytest.raises(QuestionsValidationError):
        parse_questions_payload(payload)


def test_reject_invalid_source_page_type() -> None:
    payload = _valid_payload()
    payload["questions"][0]["expected"]["sources"][0]["source_page"] = "1"
    with pytest.raises(QuestionsValidationError):
        parse_questions_payload(payload)


def test_load_questions_file_ok(tmp_path: Path) -> None:
    path = tmp_path / "questions.json"
    path.write_text(json.dumps(_valid_payload()), encoding="utf-8")
    cases = load_questions_file(path)
    assert isinstance(cases[0], QuestionCase)
    assert cases[0].expected == ExpectedResult(
        refused=False,
        sources=(
            SourceRef(
                document_id="DOC-AAAA1111",
                chunk_id="DOC-AAAA1111-C001",
                source_page=1,
            ),
        ),
    )


def test_load_missing_file(tmp_path: Path) -> None:
    with pytest.raises(QuestionsValidationError):
        load_questions_file(tmp_path / "absent.json")


def test_load_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(QuestionsValidationError):
        load_questions_file(path)

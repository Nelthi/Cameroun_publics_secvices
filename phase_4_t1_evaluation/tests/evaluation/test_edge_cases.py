"""Tests Étape 6 — cas invalides, réseau, réponses malformées."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from evaluation.ask_client import HttpAskClient, parse_ask_response
from evaluation.config import EvalConfig
from evaluation.exceptions import AskClientError, QuestionsValidationError
from evaluation.models import ExpectedResult, QuestionCase
from evaluation.questions_loader import parse_questions_payload
from evaluation.runner import run_evaluation


def _case(question: str = "Question test") -> QuestionCase:
    return QuestionCase(
        question_id="QEDGE",
        question=question,
        language="fr",
        expected=ExpectedResult(refused=False, sources=()),
    )


def _http_client(handler) -> HttpAskClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="http://test")
    config = EvalConfig(
        api_base_url="http://test",
        ask_path="/ask",
        http_timeout_seconds=5,
        ask_mode="http",
    )
    return HttpAskClient(config, client=http_client)


def test_reject_missing_question_id() -> None:
    payload = {
        "questions": [
            {
                "question": "Sans id ?",
                "language": "fr",
                "expected": {"refused": True, "sources": []},
            }
        ]
    }
    with pytest.raises(QuestionsValidationError, match="question_id"):
        parse_questions_payload(payload)


def test_reject_empty_question_text() -> None:
    payload = {
        "questions": [
            {
                "question_id": "Q001",
                "question": "   ",
                "language": "fr",
                "expected": {"refused": True, "sources": []},
            }
        ]
    }
    with pytest.raises(QuestionsValidationError, match="question"):
        parse_questions_payload(payload)


def test_reject_refused_not_bool() -> None:
    payload = {
        "questions": [
            {
                "question_id": "Q001",
                "question": "Test",
                "language": "fr",
                "expected": {"refused": "oui", "sources": []},
            }
        ]
    }
    with pytest.raises(QuestionsValidationError, match="refused"):
        parse_questions_payload(payload)


def test_parse_ask_response_invalid_types() -> None:
    with pytest.raises(AskClientError):
        parse_ask_response(
            {
                "request_id": "REQ-1",
                "answer": "x",
                "refused": "false",
                "sources": [],
                "duration_ms": 1,
            }
        )
    with pytest.raises(AskClientError):
        parse_ask_response(
            {
                "request_id": "REQ-1",
                "answer": "x",
                "refused": False,
                "sources": "DOC-1",
                "duration_ms": 1,
            }
        )
    with pytest.raises(AskClientError):
        parse_ask_response(
            {
                "request_id": "REQ-1",
                "answer": "x",
                "refused": False,
                "sources": [{"document_id": ""}],
                "duration_ms": 1,
            }
        )


def test_http_connect_error_is_not_refusal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = _http_client(handler)
    with pytest.raises(AskClientError, match="réseau"):
        client.ask(_case())


def test_http_non_json_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    client = _http_client(handler)
    with pytest.raises(AskClientError, match="non JSON"):
        client.ask(_case())


def test_runner_ask_error_goes_to_failures_not_refusal(tmp_path: Path) -> None:
    questions_path = tmp_path / "questions.json"
    questions_path.write_text(
        json.dumps(
            {
                "questions": [
                    {
                        "question_id": "QERR",
                        "question": "Question qui échoue réseau",
                        "language": "fr",
                        "expected": {"refused": True, "sources": []},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    class FailingClient:
        def ask(self, case: QuestionCase):
            raise AskClientError("Timeout simulé")

    report = run_evaluation(
        questions_path=questions_path,
        reports_dir=tmp_path / "reports",
        run_id="run_net_err",
        client=FailingClient(),
    )
    assert report.n_questions == 1
    assert len(report.failures) == 1
    assert report.failures[0].question_id == "QERR"
    assert report.failures[0].got["error_type"] == "ask_client_error"
    # Erreur réseau ≠ refus correct : dénominateur refusal non alimenté.
    assert report.metrics.correct_refusal_rate == 0.0
    assert report.metrics.avg_duration_ms == 0.0

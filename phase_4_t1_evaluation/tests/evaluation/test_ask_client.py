"""Tests Étape 3 — client POST /ask (mock, HTTP, erreurs)."""

from __future__ import annotations

import httpx
import pytest

from evaluation.ask_client import (
    HttpAskClient,
    MockAskClient,
    create_ask_client,
    parse_ask_response,
)
from evaluation.config import EvalConfig
from evaluation.exceptions import AskClientError
from evaluation.models import ExpectedResult, QuestionCase, SourceRef


def _case(
    question: str,
    *,
    refused: bool = False,
    sources: tuple[SourceRef, ...] = (),
) -> QuestionCase:
    return QuestionCase(
        question_id="QTEST",
        question=question,
        language="fr",
        expected=ExpectedResult(refused=refused, sources=sources),
    )


def test_parse_ask_response_ok() -> None:
    payload = {
        "request_id": "REQ-1",
        "answer": "ok",
        "refused": False,
        "sources": [{"document_id": "DOC-1", "source_page": 1}],
        "duration_ms": 12.5,
    }
    parsed = parse_ask_response(payload)
    assert parsed.request_id == "REQ-1"
    assert parsed.sources[0].document_id == "DOC-1"


def test_parse_ask_response_malformed() -> None:
    with pytest.raises(AskClientError):
        parse_ask_response({"request_id": "REQ-1"})


def test_mock_refuses_off_topic() -> None:
    client = MockAskClient()
    result = client.ask(_case("Donne-moi une recette de ndolé", refused=True))
    assert result.refused is True
    assert result.sources == ()
    assert result.duration_ms > 0


def test_mock_returns_expected_sources() -> None:
    sources = (SourceRef(document_id="DOC-CNI-GUIDE-001"),)
    client = MockAskClient()
    result = client.ask(
        _case(
            "Comment obtenir une CNI ?",
            refused=False,
            sources=sources,
        )
    )
    assert result.refused is False
    assert result.sources[0].document_id == "DOC-CNI-GUIDE-001"


def test_http_client_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/ask"
        assert request.method == "POST"
        return httpx.Response(
            200,
            json={
                "request_id": "REQ-HTTP-1",
                "answer": "Réponse API",
                "refused": False,
                "sources": [{"document_id": "DOC-1"}],
                "duration_ms": 5,
            },
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="http://test")
    config = EvalConfig(
        api_base_url="http://test",
        ask_path="/ask",
        http_timeout_seconds=5,
        ask_mode="http",
    )
    client = HttpAskClient(config, client=http_client)
    result = client.ask(_case("Question test"))
    assert result.request_id == "REQ-HTTP-1"
    assert result.refused is False


def test_http_client_timeout_is_not_refusal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="http://test")
    config = EvalConfig(
        api_base_url="http://test",
        ask_path="/ask",
        http_timeout_seconds=1,
        ask_mode="http",
    )
    client = HttpAskClient(config, client=http_client)
    with pytest.raises(AskClientError, match="Timeout"):
        client.ask(_case("Question lente"))


def test_http_client_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="http://test")
    config = EvalConfig(
        api_base_url="http://test",
        ask_path="/ask",
        http_timeout_seconds=5,
        ask_mode="http",
    )
    client = HttpAskClient(config, client=http_client)
    with pytest.raises(AskClientError, match="HTTP 503"):
        client.ask(_case("Question"))


def test_http_client_malformed_json_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"foo": "bar"})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="http://test")
    config = EvalConfig(
        api_base_url="http://test",
        ask_path="/ask",
        http_timeout_seconds=5,
        ask_mode="http",
    )
    client = HttpAskClient(config, client=http_client)
    with pytest.raises(AskClientError):
        client.ask(_case("Question"))


def test_create_ask_client_mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVAL_ASK_MODE", "mock")
    client = create_ask_client()
    assert isinstance(client, MockAskClient)

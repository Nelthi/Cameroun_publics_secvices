"""Tests Étape 0 — validation du contrat d'entrée T1."""

from __future__ import annotations

import pytest

from backend.orchestration import (
    DEFAULT_MAX_QUESTION_LENGTH,
    InvalidRequestError,
    RoutingPlan,
    parse_request,
)


def valid_payload(**overrides):
    data = {
        "request_id": "REQ-20261106-0001",
        "question": "Comment obtenir une carte nationale d'identité au Cameroun ?",
        "language": "fr",
        "timestamp": "2026-11-06T10:00:00",
    }
    data.update(overrides)
    return data


def test_parse_valid_request_keeps_request_id() -> None:
    result = parse_request(valid_payload())

    assert result.request_id == "REQ-20261106-0001"
    assert result.language == "fr"
    assert result.timestamp == "2026-11-06T10:00:00"
    assert "carte nationale" in result.question


def test_parse_strips_whitespace_fields() -> None:
    result = parse_request(
        valid_payload(
            request_id="  REQ-20261106-0002  ",
            question="  Bonjour  ",
            language="  fr  ",
        )
    )

    assert result.request_id == "REQ-20261106-0002"
    assert result.question == "Bonjour"
    assert result.language == "fr"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        "pas un dict",
        42,
    ],
)
def test_reject_malformed_request_container(payload) -> None:
    with pytest.raises(InvalidRequestError):
        parse_request(payload)


@pytest.mark.parametrize(
    "missing_field",
    ["request_id", "question", "language", "timestamp"],
)
def test_reject_missing_required_field(missing_field: str) -> None:
    payload = valid_payload()
    del payload[missing_field]

    with pytest.raises(InvalidRequestError) as exc_info:
        parse_request(payload)

    assert missing_field in str(exc_info.value)


@pytest.mark.parametrize(
    "field",
    ["request_id", "question", "language", "timestamp"],
)
def test_reject_empty_or_blank_field(field: str) -> None:
    with pytest.raises(InvalidRequestError):
        parse_request(valid_payload(**{field: "   "}))


def test_reject_non_string_question() -> None:
    with pytest.raises(InvalidRequestError):
        parse_request(valid_payload(question=123))


def test_reject_invalid_timestamp() -> None:
    with pytest.raises(InvalidRequestError):
        parse_request(valid_payload(timestamp="06/11/2026 10:00"))


def test_accept_iso_timestamp_with_timezone_offset() -> None:
    result = parse_request(
        valid_payload(timestamp="2026-11-06T10:00:00+01:00")
    )
    assert result.timestamp == "2026-11-06T10:00:00+01:00"


def test_reject_unexpected_fields() -> None:
    with pytest.raises(InvalidRequestError):
        parse_request(valid_payload(extra_field="interdit"))


def test_reject_question_too_long() -> None:
    long_question = "a" * (DEFAULT_MAX_QUESTION_LENGTH + 1)

    with pytest.raises(InvalidRequestError):
        parse_request(valid_payload(question=long_question))


def test_accept_question_at_max_length() -> None:
    question = "é" * DEFAULT_MAX_QUESTION_LENGTH
    result = parse_request(valid_payload(question=question))
    assert len(result.question) == DEFAULT_MAX_QUESTION_LENGTH


def test_routing_plan_to_dict_matches_official_contract() -> None:
    plan = RoutingPlan(
        request_id="REQ-20261106-0001",
        intent="procedure",
        domain="public_services",
        subdomain="national_identity_card",
        agents=("procedure",),
        needs_clarification=False,
    )

    payload = plan.to_dict()

    assert set(payload.keys()) == {
        "request_id",
        "intent",
        "domain",
        "subdomain",
        "agents",
        "needs_clarification",
    }
    assert payload == {
        "request_id": "REQ-20261106-0001",
        "intent": "procedure",
        "domain": "public_services",
        "subdomain": "national_identity_card",
        "agents": ["procedure"],
        "needs_clarification": False,
    }

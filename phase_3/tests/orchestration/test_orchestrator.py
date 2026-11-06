"""Tests Étape 6 — orchestrateur et route_question."""

from __future__ import annotations

import pytest

from backend.orchestration import route_question
from backend.orchestration.exceptions import InvalidRequestError
from backend.orchestration.orchestrator import build_routing_plan


def _request(question: str, request_id: str = "REQ-20261106-0001") -> dict:
    return {
        "request_id": request_id,
        "question": question,
        "language": "fr",
        "timestamp": "2026-11-06T10:00:00",
    }


CONTRACT_KEYS = {
    "request_id",
    "intent",
    "domain",
    "subdomain",
    "agents",
    "needs_clarification",
}


def test_route_question_official_example() -> None:
    payload = route_question(
        _request(
            "Comment obtenir une carte nationale d'identité au Cameroun ?"
        )
    )

    assert set(payload.keys()) == CONTRACT_KEYS
    assert payload["request_id"] == "REQ-20261106-0001"
    assert payload["intent"] == "procedure"
    assert payload["domain"] == "public_services"
    assert payload["subdomain"] == "national_identity_card"
    assert payload["agents"] == ["procedure"]
    assert payload["needs_clarification"] is False


@pytest.mark.parametrize(
    ("question", "intent"),
    [
        ("Bonjour, qui êtes-vous ?", "accueil"),
        ("Quelle est la base légale de la CNI ?", "juridique"),
        ("Comment protéger mes données personnelles ?", "donnees_personnelles"),
        ("Donne-moi une recette de cuisine", "hors_sujet"),
        ("Quel délai pour un passeport ?", "procedure"),
    ],
)
def test_route_question_covers_intents(question: str, intent: str) -> None:
    payload = route_question(_request(question, request_id="REQ-TEST-INT"))
    assert payload["intent"] == intent
    assert set(payload.keys()) == CONTRACT_KEYS
    assert payload["request_id"] == "REQ-TEST-INT"


def test_preserves_request_id_from_t4() -> None:
    payload = route_question(_request("Merci", request_id="REQ-20261106-9999"))
    assert payload["request_id"] == "REQ-20261106-9999"


def test_vague_question_needs_clarification() -> None:
    payload = route_question(_request("Comment faire ?"))
    assert payload["needs_clarification"] is True
    assert payload["intent"] != "hors_sujet" or payload["needs_clarification"] is True


def test_hors_sujet_has_empty_agents_and_no_clarification() -> None:
    payload = route_question(_request("Score du match de football hier ?"))
    assert payload["intent"] == "hors_sujet"
    assert payload["agents"] == []
    assert payload["needs_clarification"] is False


def test_unknown_domain_when_no_signal() -> None:
    payload = route_question(_request("Bonjour, qui êtes-vous ?"))
    assert payload["domain"] == "unknown"
    assert payload["subdomain"] == "unknown"


def test_multi_agent_possible_for_mixed_question() -> None:
    payload = route_question(
        _request("Quelle loi régit la procédure d'obtention de la CNI ?")
    )
    assert payload["intent"] == "juridique"
    assert "juridique" in payload["agents"]
    assert 1 <= len(payload["agents"]) <= 3


def test_build_routing_plan_returns_model() -> None:
    plan = build_routing_plan(_request("Renouveler ma CNI"))
    assert plan.intent == "procedure"
    assert plan.to_dict()["agents"]


def test_invalid_request_raises() -> None:
    with pytest.raises(InvalidRequestError):
        route_question({"question": "test"})


def test_empty_question_raises() -> None:
    with pytest.raises(InvalidRequestError):
        route_question(_request("   "))


def test_no_extra_fields_in_output() -> None:
    payload = route_question(_request("Obtenir un acte de naissance"))
    assert list(payload.keys()) == [
        "request_id",
        "intent",
        "domain",
        "subdomain",
        "agents",
        "needs_clarification",
    ]

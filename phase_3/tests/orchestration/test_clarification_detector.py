"""Tests Étape 4 — détection de clarification."""

from __future__ import annotations

import pytest

from backend.orchestration.clarification_detector import needs_clarification
from backend.orchestration.exceptions import InvalidRequestError


@pytest.mark.parametrize(
    "question",
    [
        "Comment faire ?",
        "J'ai un problème.",
        "Je veux le document.",
        "Que faire ?",
        "Aide-moi",
        "Je suis perdu",
    ],
)
def test_vague_questions_need_clarification(question: str) -> None:
    assert needs_clarification(question, intent="procedure", domain="unknown") is True


@pytest.mark.parametrize(
    "question",
    [
        "Comment obtenir une carte nationale d'identité au Cameroun ?",
        "Quel est le délai pour renouveler un passeport ?",
        "Quelle est la base légale de la CNI ?",
        "Comment protéger mes données personnelles ?",
        "Bonjour, qui êtes-vous ?",
    ],
)
def test_precise_questions_do_not_need_clarification(question: str) -> None:
    assert (
        needs_clarification(
            question,
            intent="procedure",
            domain="public_services",
        )
        is False
    )


@pytest.mark.parametrize(
    "question",
    [
        "Donne-moi une recette de cuisine",
        "Quel est le score du match de football ?",
        "Parle-moi de bitcoin",
    ],
)
def test_hors_sujet_is_not_clarification(question: str) -> None:
    # Hors sujet clair ≠ question ambiguë.
    assert needs_clarification(question, intent="hors_sujet", domain="unknown") is False


def test_short_question_without_domain_needs_clarification() -> None:
    assert needs_clarification("Et après ?", intent="accueil", domain="unknown") is True


def test_short_but_domain_known_may_skip_clarification() -> None:
    # « Ma CNI ? » est courte mais le domaine est identifiable.
    assert (
        needs_clarification("Ma CNI ?", intent="procedure", domain="public_services")
        is False
    )


def test_empty_question_rejected() -> None:
    with pytest.raises(InvalidRequestError):
        needs_clarification("   ")

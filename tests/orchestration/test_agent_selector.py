"""Tests Étape 5 — sélection des agents."""

from __future__ import annotations

import pytest

from backend.orchestration.agent_selector import (
    select_agents,
    select_agents_for_intent,
)
from backend.orchestration.exceptions import InvalidRequestError


@pytest.mark.parametrize(
    ("intent", "expected"),
    [
        ("accueil", ["accueil"]),
        ("procedure", ["procedure"]),
        ("juridique", ["juridique"]),
        ("donnees_personnelles", ["donnees_personnelles"]),
        ("hors_sujet", []),
    ],
)
def test_primary_agent_from_intent(intent: str, expected: list[str]) -> None:
    assert select_agents_for_intent(intent) == expected  # type: ignore[arg-type]


def test_select_agents_between_one_and_three_for_business_intent() -> None:
    agents = select_agents(
        "procedure",
        "Quelle loi régit la procédure d'obtention de la CNI ?",
    )
    assert 1 <= len(agents) <= 3
    assert "procedure" in agents
    assert "juridique" in agents


def test_no_duplicate_agents() -> None:
    agents = select_agents(
        "juridique",
        "Quelle loi pour la procédure CNI et mes données personnelles ?",
    )
    assert len(agents) == len(set(agents))
    assert len(agents) <= 3


def test_hors_sujet_returns_empty_even_with_question() -> None:
    assert select_agents("hors_sujet", "recette de cuisine") == []


def test_custom_mapping() -> None:
    mapping = {
        "procedure": ("agent_procedure", "agent_docs"),
        "accueil": (),
        "juridique": (),
        "donnees_personnelles": (),
        "hors_sujet": (),
    }
    assert select_agents("procedure", intent_to_agents=mapping) == [
        "agent_procedure",
        "agent_docs",
    ]


def test_unknown_intent_rejected() -> None:
    with pytest.raises(InvalidRequestError):
        select_agents("inconnu")

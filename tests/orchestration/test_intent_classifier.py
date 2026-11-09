"""Tests Étape 2 — classification d'intentions (≥ 10 questions, 5 intents)."""

from __future__ import annotations

import pytest

from backend.orchestration.exceptions import InvalidRequestError
from backend.orchestration.intent_classifier import classify_intent, score_intents


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        # accueil
        ("Bonjour, qui êtes-vous ?", "accueil"),
        ("Merci pour votre aide", "accueil"),
        # procedure
        (
            "Comment obtenir une carte nationale d'identité au Cameroun ?",
            "procedure",
        ),
        ("Quelles pièces à fournir pour un passeport ?", "procedure"),
        ("Quel est le délai pour renouveler une CNI ?", "procedure"),
        ("Où déposer mon dossier d'acte de naissance ?", "procedure"),
        # juridique
        ("Quelle est la base légale de la CNI ?", "juridique"),
        ("Y a-t-il un décret qui réglemente le passeport ?", "juridique"),
        # donnees_personnelles
        ("Comment protéger mes données personnelles ?", "donnees_personnelles"),
        ("Puis-je demander la suppression de mes données (RGPD) ?", "donnees_personnelles"),
        # hors_sujet
        ("Donne-moi une recette de cuisine camerounaise", "hors_sujet"),
        ("Quel est le score du match de football hier ?", "hors_sujet"),
        # aucun mot-clé métier → hors_sujet
        ("Parle-moi des étoiles dans le ciel", "hors_sujet"),
    ],
)
def test_classify_ten_plus_questions_across_five_intents(
    question: str,
    expected: str,
) -> None:
    assert classify_intent(question) == expected


def test_accents_and_natural_phrasing() -> None:
    assert classify_intent("Comment obtenir une carte d’identité ?") == "procedure"
    assert classify_intent("Quelle réglementation s’applique ?") == "juridique"


def test_multi_intent_priority_donnees_over_procedure() -> None:
    # Contient « obtenir » (procedure) et « données personnelles ».
    question = "Comment obtenir l'accès à mes données personnelles ?"
    assert classify_intent(question) == "donnees_personnelles"


def test_multi_intent_priority_juridique_over_procedure() -> None:
    question = "Quelle loi régit la procédure d'obtention de la CNI ?"
    assert classify_intent(question) == "juridique"


def test_score_intents_reports_matches() -> None:
    scores = {
        item.intent: item for item in score_intents("renouveler ma CNI")
    }
    assert scores["procedure"].score >= 1
    assert "cni" in scores["procedure"].matched_keywords or (
        "renouveler" in scores["procedure"].matched_keywords
    )


def test_custom_keywords_override() -> None:
    custom = {
        "accueil": ("hey",),
        "procedure": (),
        "juridique": (),
        "donnees_personnelles": (),
        "hors_sujet": (),
    }
    assert classify_intent("hey assistant", keywords=custom) == "accueil"


def test_empty_question_rejected() -> None:
    with pytest.raises(InvalidRequestError):
        classify_intent("   ")

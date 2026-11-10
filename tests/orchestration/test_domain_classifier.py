"""Tests Étape 3 — classification domaine / sous-domaine."""

from __future__ import annotations

import pytest

from backend.orchestration.config import UNKNOWN_DOMAIN, UNKNOWN_SUBDOMAIN
from backend.orchestration.domain_classifier import (
    classify_domain,
    score_domains,
)
from backend.orchestration.exceptions import InvalidRequestError


@pytest.mark.parametrize(
    ("question", "domain", "subdomain"),
    [
        (
            "Comment obtenir une carte nationale d'identité au Cameroun ?",
            "public_services",
            "national_identity_card",
        ),
        (
            "Quel délai pour renouveler ma CNI ?",
            "public_services",
            "national_identity_card",
        ),
        (
            "Quelles pièces pour un passeport ?",
            "public_services",
            "passport",
        ),
        (
            "Comment demander un acte de naissance ?",
            "public_services",
            "birth_certificate",
        ),
        (
            "Où retirer un extrait de naissance ?",
            "public_services",
            "birth_certificate",
        ),
    ],
)
def test_known_domains(question: str, domain: str, subdomain: str) -> None:
    result = classify_domain(question)
    assert result.domain == domain
    assert result.subdomain == subdomain


@pytest.mark.parametrize(
    "question",
    [
        "Bonjour, qui êtes-vous ?",
        "Donne-moi une recette de cuisine",
        "Parle-moi des étoiles",
        "Comment faire ?",
    ],
)
def test_unknown_when_insufficient_information(question: str) -> None:
    result = classify_domain(question)
    assert result.domain == UNKNOWN_DOMAIN
    assert result.subdomain == UNKNOWN_SUBDOMAIN


def test_accents_do_not_block_cni_detection() -> None:
    result = classify_domain("Obtenir une carte d’identité nationale")
    assert result.domain == "public_services"
    assert result.subdomain == "national_identity_card"


def test_custom_domain_config_is_extensible() -> None:
    custom = {
        "education": {
            "exams": ("baccalaureat", "concours"),
        }
    }
    result = classify_domain(
        "Comment s'inscrire au concours ?",
        domain_keywords=custom,
    )
    assert result.domain == "education"
    assert result.subdomain == "exams"


def test_score_domains_lists_matches() -> None:
    matches = score_domains("renouveler passeport et CNI")
    subdomains = {item.subdomain for item in matches}
    assert "passport" in subdomains
    assert "national_identity_card" in subdomains


def test_empty_question_rejected() -> None:
    with pytest.raises(InvalidRequestError):
        classify_domain("  ")

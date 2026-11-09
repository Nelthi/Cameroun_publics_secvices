"""Classification domaine / sous-domaine (règles configurables)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .config import (
    DOMAIN_KEYWORDS,
    UNKNOWN_DOMAIN,
    UNKNOWN_SUBDOMAIN,
)
from .exceptions import InvalidRequestError
from .question_cleaner import clean_question, fold_accents


@dataclass(frozen=True)
class DomainMatch:
    domain: str
    subdomain: str
    score: int
    matched_keywords: tuple[str, ...]


@dataclass(frozen=True)
class DomainClassification:
    domain: str
    subdomain: str


def _normalize_for_match(text: str) -> str:
    return fold_accents(clean_question(text))


def score_domains(
    question: str,
    *,
    domain_keywords: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
) -> list[DomainMatch]:
    """Score chaque couple (domain, subdomain) présent dans la config."""
    if not isinstance(question, str) or not question.strip():
        raise InvalidRequestError("question vide pour la classification domaine.")

    normalized = _normalize_for_match(question)
    source = domain_keywords if domain_keywords is not None else DOMAIN_KEYWORDS
    matches: list[DomainMatch] = []

    for domain, subdomains in source.items():
        for subdomain, patterns in subdomains.items():
            matched = [
                pattern
                for pattern in patterns
                if fold_accents(str(pattern).lower()) in normalized
            ]
            if matched:
                matches.append(
                    DomainMatch(
                        domain=domain,
                        subdomain=subdomain,
                        score=len(matched),
                        matched_keywords=tuple(matched),
                    )
                )

    return matches


def classify_domain(
    question: str,
    *,
    domain_keywords: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
) -> DomainClassification:
    """Identifie domain + subdomain, ou unknown si information insuffisante.

    Règles :
    - Match sous-chaîne sur texte nettoyé / sans accents.
    - On retient le couple avec le meilleur score.
    - En cas d'égalité, le motif le plus long (join des keywords) départage
      pour favoriser les expressions plus précises.
    - Aucun match → domain=unknown, subdomain=unknown (pas d'invention).
    """
    matches = score_domains(question, domain_keywords=domain_keywords)
    if not matches:
        return DomainClassification(
            domain=UNKNOWN_DOMAIN,
            subdomain=UNKNOWN_SUBDOMAIN,
        )

    def sort_key(item: DomainMatch) -> tuple[int, int, str, str]:
        longest = max((len(k) for k in item.matched_keywords), default=0)
        return (-item.score, -longest, item.domain, item.subdomain)

    matches.sort(key=sort_key)
    best = matches[0]
    return DomainClassification(domain=best.domain, subdomain=best.subdomain)

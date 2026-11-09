"""Contrats d'entrée et de sortie T1 Phase 3 (snake_case, ISO 8601).

Contrat d'entrée (T4 → T1) :
  request_id, question, language, timestamp

Contrat de sortie (T1 → T2/T4) — champs stricts :
  request_id, intent, domain, subdomain, agents, needs_clarification
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from .exceptions import InvalidRequestError

IntentName = Literal[
    "accueil",
    "procedure",
    "juridique",
    "donnees_personnelles",
    "hors_sujet",
]

# Limite proposée (non fixée dans le guide) — à ajuster avec l'équipe.
DEFAULT_MAX_QUESTION_LENGTH = 1000

ALLOWED_INTENTS: frozenset[str] = frozenset(
    {
        "accueil",
        "procedure",
        "juridique",
        "donnees_personnelles",
        "hors_sujet",
    }
)


@dataclass(frozen=True)
class RequestInput:
    """Requête reçue de T4."""

    request_id: str
    question: str
    language: str
    timestamp: str

    def to_dict(self) -> dict[str, str]:
        return {
            "request_id": self.request_id,
            "question": self.question,
            "language": self.language,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class RoutingPlan:
    """Plan de routage officiel — aucun champ supplémentaire autorisé."""

    request_id: str
    intent: IntentName
    domain: str
    subdomain: str
    agents: tuple[str, ...]
    needs_clarification: bool

    def to_dict(self) -> dict[str, Any]:
        """Sérialise exactement le contrat de sortie Phase 3."""
        return {
            "request_id": self.request_id,
            "intent": self.intent,
            "domain": self.domain,
            "subdomain": self.subdomain,
            "agents": list(self.agents),
            "needs_clarification": self.needs_clarification,
        }


def _require_non_empty_string(payload: dict[str, Any], field: str) -> str:
    if field not in payload:
        raise InvalidRequestError(f"Champ obligatoire manquant : {field}")
    value = payload[field]
    if not isinstance(value, str):
        raise InvalidRequestError(f"Le champ {field} doit être une chaîne.")
    cleaned = value.strip()
    if not cleaned:
        raise InvalidRequestError(f"Le champ {field} ne peut pas être vide.")
    return cleaned


def _validate_iso_timestamp(value: str) -> str:
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise InvalidRequestError(
            "timestamp doit respecter le format ISO 8601 "
            "(ex. 2026-11-06T10:00:00)."
        ) from exc
    return value


def parse_request(
    request_data: Any,
    *,
    max_question_length: int = DEFAULT_MAX_QUESTION_LENGTH,
) -> RequestInput:
    """Valide et normalise le contrat d'entrée T1.

    Conserve request_id tel que fourni par T4 (après strip).
    """
    if not isinstance(request_data, dict):
        raise InvalidRequestError(
            "La requête doit être un objet JSON (dict Python)."
        )

    unexpected = set(request_data) - {
        "request_id",
        "question",
        "language",
        "timestamp",
    }
    # Les champs supplémentaires ne sont pas dans le contrat : on les refuse
    # pour éviter une dérive silencieuse entre T4 et T1.
    if unexpected:
        raise InvalidRequestError(
            "Champs non autorisés dans la requête : "
            + ", ".join(sorted(unexpected))
        )

    request_id = _require_non_empty_string(request_data, "request_id")
    question = _require_non_empty_string(request_data, "question")
    language = _require_non_empty_string(request_data, "language")
    timestamp = _validate_iso_timestamp(
        _require_non_empty_string(request_data, "timestamp")
    )

    if max_question_length <= 0:
        raise ValueError("max_question_length doit être strictement positif.")
    if len(question) > max_question_length:
        raise InvalidRequestError(
            f"question trop longue : {len(question)} caractères "
            f"(maximum {max_question_length})."
        )

    return RequestInput(
        request_id=request_id,
        question=question,
        language=language,
        timestamp=timestamp,
    )

"""Structures internes : une observation = un signalement de lacune (audit ou évaluation)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Observation:
    topic: str                      # libellé du sujet non couvert (déjà nettoyé)
    origin: str                     # "audit" ou "eval"
    weight: int = 1                 # occurrences représentées (0 = confirme une lacune déjà comptée)
    reason: str | None = None       # raison de la lacune (audit)
    failure_type: str | None = None # type d'échec (évaluation)
    request_id: str | None = None
    question_id: str | None = None
    question: str | None = None     # question du citoyen, masquée
    timestamp: datetime | None = None
    domain: str | None = None
    subdomain: str | None = None


@dataclass
class AuditContext:
    """Ce que le journal d'audit sait d'une requête : sa question et son routage."""
    question: str | None = None
    domain: str | None = None
    subdomain: str | None = None


@dataclass
class AuditData:
    observations: list[Observation] = field(default_factory=list)
    contexts: dict[str, AuditContext] = field(default_factory=dict)  # request_id -> contexte
    info: dict = field(default_factory=dict)


@dataclass
class EvalData:
    run_id: str | None
    failures: list[dict]
    info: dict = field(default_factory=dict)

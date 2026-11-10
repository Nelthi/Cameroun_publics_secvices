"""Sélection de 1 à 3 agents spécialisés (T1 Phase 3).

Les noms d'agents suivent les exemples du guide Phase 3
(procedure, juridique, …). Ils restent configurables dans config.py
en attendant la convention définitive de l'équipe T2.
"""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

from .config import (
    INTENT_TO_AGENTS,
    MAX_AGENTS,
    SECONDARY_INTENT_AGENTS,
)
from .exceptions import InvalidRequestError
from .intent_classifier import score_intents
from .models import ALLOWED_INTENTS, IntentName


def select_agents(
    intent: str,
    question: Optional[str] = None,
    *,
    intent_to_agents: Mapping[str, Sequence[str]] | None = None,
    max_agents: int = MAX_AGENTS,
) -> list[str]:
    """Retourne entre 0 et max_agents agents (0 seulement pour hors_sujet).

    Règles :
    1. L'agent principal dérive de l'intention primaire (INTENT_TO_AGENTS).
    2. Si une question est fournie, on peut ajouter des agents liés à
       d'autres intentions qui matchent aussi (score > 0), sans dépasser
       max_agents (défaut 3).
    3. Ordre stable, sans doublon.
    4. hors_sujet → liste vide.
    """
    if intent not in ALLOWED_INTENTS:
        raise InvalidRequestError(f"Intention inconnue : {intent}")
    if max_agents < 1:
        raise ValueError("max_agents doit être >= 1.")

    mapping = intent_to_agents if intent_to_agents is not None else INTENT_TO_AGENTS
    primary = list(mapping.get(intent, ()))

    if intent == "hors_sujet":
        return []

    selected: list[str] = []
    for agent in primary:
        if agent not in selected:
            selected.append(agent)

    if question and len(selected) < max_agents:
        scores = {
            item.intent: item.score
            for item in score_intents(question)
            if item.score > 0 and item.intent != intent
        }
        for secondary_intent in SECONDARY_INTENT_AGENTS:
            if len(selected) >= max_agents:
                break
            if scores.get(secondary_intent, 0) <= 0:
                continue
            for agent in mapping.get(secondary_intent, ()):
                if agent not in selected:
                    selected.append(agent)
                if len(selected) >= max_agents:
                    break

    # Contrat : entre 1 et 3 agents pour les intentions métier.
    if not selected:
        # Filet de sécurité si la config primaire est vide par erreur.
        selected = [intent]

    return selected[:max_agents]


def select_agents_for_intent(intent: IntentName) -> list[str]:
    """Raccourci : agents uniquement à partir de l'intention primaire."""
    return select_agents(intent, question=None)

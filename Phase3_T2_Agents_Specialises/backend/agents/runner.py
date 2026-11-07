"""Orchestration de T2 : plan de routage T1 + question -> brouillons des agents.

    from backend.agents import run_agents
    drafts = run_agents(question, routing_plan, language="fr")   # liste de brouillons (contrat T2)
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Callable

from .agents import (AccueilAgent, AntiFraudeAgent, DonneesPersonnellesAgent, JuridiqueAgent,
                     ProcedureAgent)
from .base import DEFAULT_TOP_K, Agent, make_draft
from .exceptions import AgentError, ContractError, UnknownAgentError
from .messages import NO_ANSWER, normalize_language

logger = logging.getLogger(__name__)

MAX_AGENTS = 3  # « Choisir les agents à appeler (1 à 3) » : guide, tâche T1

AGENT_CLASSES: dict[str, type[Agent]] = {
    cls.name: cls
    for cls in (AccueilAgent, ProcedureAgent, JuridiqueAgent, DonneesPersonnellesAgent, AntiFraudeAgent)
}

# Noms alternatifs acceptés dans le plan de T1 (après normalisation : minuscules, sans accent, « _ »).
ALIASES = {
    "protection_donnees": "donnees_personnelles",
    "protection_des_donnees": "donnees_personnelles",
    "donnees": "donnees_personnelles",
    "data_protection": "donnees_personnelles",
    "antifraude": "anti_fraude",
    "fraude": "anti_fraude",
    "fraud": "anti_fraude",
    "legal": "juridique",
    "welcome": "accueil",
}

# Rôles qui existent dans le projet mais ne relèvent pas de T2 (assemblage final : T3/T4).
NOT_T2 = {"coordinateur", "coordinator"}

# Intentions qui ne nécessitent aucune recherche : l'agent d'accueil répond seul.
STATIC_INTENTS = {"accueil", "hors_sujet"}


def canonical_agent_name(name) -> str:
    """'Protection-des-données' -> 'donnees_personnelles' ; lève UnknownAgentError si inconnu."""
    if not isinstance(name, str) or not name.strip():
        raise UnknownAgentError(f"nom d'agent invalide : {name!r}")
    folded = unicodedata.normalize("NFKD", name.strip().casefold())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    folded = re.sub(r"[\s\-]+", "_", folded)
    folded = ALIASES.get(folded, folded)
    if folded not in AGENT_CLASSES:
        raise UnknownAgentError(f"agent inconnu : {name!r} (agents : {', '.join(AGENT_CLASSES)})")
    return folded


def validate_plan(plan) -> None:
    """Vérifie le strict nécessaire du plan de routage T1 (contrat du guide)."""
    if not isinstance(plan, dict):
        raise ContractError("le plan de routage doit être un objet JSON")
    if not isinstance(plan.get("request_id"), str) or not plan["request_id"].strip():
        raise ContractError("plan de routage : 'request_id' manquant")
    if not isinstance(plan.get("intent"), str):
        raise ContractError("plan de routage : 'intent' manquant")
    if not isinstance(plan.get("agents", []), list):
        raise ContractError("plan de routage : 'agents' doit être une liste")


def select_agents(plan: dict, strict: bool = False) -> list[str]:
    """Noms canoniques des agents à lancer, dans l'ordre du plan, sans doublon, 3 au plus."""
    if plan.get("needs_clarification") is True or plan.get("intent") in STATIC_INTENTS:
        return ["accueil"]
    selected: list[str] = []
    for raw in plan.get("agents") or []:
        if isinstance(raw, str) and raw.strip().casefold() in NOT_T2:
            logger.info("agent '%s' ignoré : hors périmètre T2", raw)
            continue
        try:
            name = canonical_agent_name(raw)
        except UnknownAgentError:
            if strict:
                raise
            logger.warning("agent inconnu ignoré dans le plan : %r", raw)
            continue
        if name not in selected:
            selected.append(name)
    if len(selected) > MAX_AGENTS:
        logger.warning("plan avec %d agents : on garde les %d premiers", len(selected), MAX_AGENTS)
        selected = selected[:MAX_AGENTS]
    return selected


def run_agents(question: str, routing_plan: dict, *, language: str | None = None,
               search_fn: Callable | None = None, llm_fn: Callable[[str], str] | None = None,
               top_k: int = DEFAULT_TOP_K, strict: bool = False) -> list[dict]:
    """Lance les agents choisis par T1 et renvoie leurs brouillons (un par agent, ordre du plan).

    - Un agent qui échoue (recherche ou LLM) donne un brouillon d'erreur (meta.kind = "error",
      meta.error = message, aucune citation) au lieu de faire tomber toute la requête ;
      avec strict=True, l'exception est levée.
    - La recherche est faite une seule fois par requête distincte, même si plusieurs agents
      posent la même.
    - Liste vide si le plan ne désigne aucun agent exploitable.
    """
    validate_plan(routing_plan)
    language = normalize_language(language if language is not None else routing_plan.get("language"))

    cache: dict[tuple[str, int], list] = {}

    def cached_search(query: str, k: int):
        key = (query, k)
        if key not in cache:
            if search_fn is not None:
                cache[key] = search_fn(query, k)
            else:
                from backend.rag import search  # import différé
                cache[key] = search(query, top_k=k)
        return cache[key]

    drafts = []
    for name in select_agents(routing_plan, strict=strict):
        agent = AGENT_CLASSES[name](search_fn=cached_search, llm_fn=llm_fn, top_k=top_k)
        try:
            drafts.append(agent.run(question, routing_plan, language))
        except ContractError:
            raise  # question vide : erreur de l'appelant, pas de l'agent
        except AgentError as exc:
            if strict:
                raise
            logger.error("agent %s en échec : %s", name, exc)
            drafts.append(make_draft(routing_plan["request_id"], name, NO_ANSWER[language], [], [],
                                     {"kind": "error", "error": str(exc), "language": language,
                                      "no_answer": True}))
    return drafts

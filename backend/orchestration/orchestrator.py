"""Orchestrateur T1 Phase 3 — assemblage du plan de routage.

Ne appelle ni T2, ni T3, ni T4. Expose uniquement route_question()
pour être consommé plus tard par T4.
"""

from __future__ import annotations

from typing import Any

from .agent_selector import select_agents
from .clarification_detector import needs_clarification
from .domain_classifier import classify_domain
from .intent_classifier import classify_intent
from .models import RoutingPlan, parse_request
from .question_cleaner import clean_question


def build_routing_plan(request_data: dict[str, Any]) -> RoutingPlan:
    """Enchaîne validation → clean → intent → domain → agents → clarification."""
    request = parse_request(request_data)
    cleaned = clean_question(request.question)

    intent = classify_intent(cleaned)
    domain_result = classify_domain(cleaned)
    agents = select_agents(intent, cleaned)
    clarification = needs_clarification(
        cleaned,
        intent=intent,
        domain=domain_result.domain,
    )

    return RoutingPlan(
        request_id=request.request_id,
        intent=intent,
        domain=domain_result.domain,
        subdomain=domain_result.subdomain,
        agents=tuple(agents),
        needs_clarification=clarification,
    )


def route_question(request_data: dict[str, Any]) -> dict[str, Any]:
    """Point d'entrée public T1 Phase 3.

    Entrée : contrat T4 (request_id, question, language, timestamp).
    Sortie : plan de routage officiel (6 champs stricts).
    """
    return build_routing_plan(request_data).to_dict()

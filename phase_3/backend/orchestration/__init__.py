"""T1 Phase 3 — Orchestrateur et Routage.

Point d'entrée public pour T4 : route_question(request_data).
"""

from .agent_selector import select_agents, select_agents_for_intent
from .clarification_detector import needs_clarification
from .domain_classifier import DomainClassification, classify_domain
from .exceptions import InvalidRequestError, OrchestrationError
from .intent_classifier import classify_intent, score_intents
from .models import (
    ALLOWED_INTENTS,
    DEFAULT_MAX_QUESTION_LENGTH,
    RequestInput,
    RoutingPlan,
    parse_request,
)
from .orchestrator import build_routing_plan, route_question
from .question_cleaner import clean_question, fold_accents

__all__ = [
    "ALLOWED_INTENTS",
    "DEFAULT_MAX_QUESTION_LENGTH",
    "DomainClassification",
    "InvalidRequestError",
    "OrchestrationError",
    "RequestInput",
    "RoutingPlan",
    "build_routing_plan",
    "classify_domain",
    "classify_intent",
    "clean_question",
    "fold_accents",
    "needs_clarification",
    "parse_request",
    "route_question",
    "score_intents",
    "select_agents",
    "select_agents_for_intent",
]

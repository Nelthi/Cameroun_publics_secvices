"""T2 — Agents spécialisés (Phase 3).

Entrée  : la question + le plan de routage de T1 + search() de la Phase 2.
Sortie  : un brouillon sourcé par agent (contrat : voir contract.py et RAPPORT_T2.md).

    from backend.agents import run_agents, merge_drafts
    drafts = run_agents(question, plan)        # 1 à 3 brouillons
    draft = merge_drafts(drafts)               # 1 brouillon, à transmettre à T3
"""
from .agents import (AccueilAgent, AntiFraudeAgent, DonneesPersonnellesAgent, JuridiqueAgent,
                     ProcedureAgent)
from .base import Agent
from .contract import validate_draft
from .exceptions import (AgentError, ContractError, LLMError, LLMNotConfiguredError, RetrievalError,
                         UnknownAgentError)
from .llm import llm_generate, set_llm
from .merge import merge_drafts
from .runner import AGENT_CLASSES, canonical_agent_name, run_agents, select_agents

__all__ = [
    "Agent", "AccueilAgent", "ProcedureAgent", "JuridiqueAgent", "DonneesPersonnellesAgent",
    "AntiFraudeAgent", "run_agents", "select_agents", "canonical_agent_name", "AGENT_CLASSES",
    "merge_drafts", "validate_draft", "llm_generate", "set_llm",
    "AgentError", "ContractError", "LLMError", "LLMNotConfiguredError", "RetrievalError",
    "UnknownAgentError",
]

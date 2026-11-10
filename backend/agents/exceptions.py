"""Exceptions de la tâche T2 (agents spécialisés)."""


class AgentError(Exception):
    """Erreur de base des agents."""


class ContractError(AgentError):
    """Entrée ou sortie qui ne respecte pas le contrat JSON (plan T1, brouillon T2...)."""


class UnknownAgentError(AgentError):
    """Nom d'agent inconnu dans le plan de routage."""


class RetrievalError(AgentError):
    """La recherche de passages (Phase 2, search) a échoué ou renvoie un format invalide."""


class LLMError(AgentError):
    """Le point d'entrée LLM a échoué (réseau, quota, réponse vide...)."""


class LLMNotConfiguredError(LLMError):
    """Aucun LLM n'est configuré (variables d'environnement absentes)."""

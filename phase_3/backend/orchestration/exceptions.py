"""Exceptions du module T1 Phase 3 — Orchestrateur et Routage."""


class OrchestrationError(Exception):
    """Erreur de base de l'orchestrateur."""


class InvalidRequestError(OrchestrationError):
    """Requête d'entrée manquante, mal formée ou invalide."""

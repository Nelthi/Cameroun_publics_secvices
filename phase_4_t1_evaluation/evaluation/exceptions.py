"""Exceptions du module d'évaluation Phase 4 T1."""


class EvaluationError(Exception):
    """Erreur de base du module evaluation."""


class QuestionsValidationError(EvaluationError):
    """Fichier questions.json invalide ou mal formé."""


class AskClientError(EvaluationError):
    """Erreur d'appel à POST /ask (réseau, timeout, HTTP, payload)."""


class ReportWriteError(EvaluationError):
    """Écriture de rapport impossible (chemin, permissions, écrasement)."""

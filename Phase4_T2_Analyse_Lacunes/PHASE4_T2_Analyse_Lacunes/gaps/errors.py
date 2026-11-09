"""Exceptions de la tâche T2 de la Phase 4."""


class GapAnalysisError(Exception):
    """Erreur de base."""


class SourceError(GapAnalysisError):
    """Une source de données (audit.db, GET /gaps, eval_report.json) est absente ou illisible."""


class ReportError(GapAnalysisError):
    """Le rapport produit ne respecte pas le contrat."""

"""T2 — Analyse des lacunes (Phase 4).

Entrées : lacunes de l'audit (audit.db ou GET /gaps) + échecs de eval_report.json (T1).
Sortie  : data/reports/gap_report.json (lu par T3 pour combler, par T4 pour la page Qualité).

    from gaps import run
    report, path = run(audit_db="data/audit.db", eval_report="data/reports/eval_report.json")
"""
from .analyzer import analyze
from .errors import GapAnalysisError, ReportError, SourceError
from .pipeline import run
from .report import validate_report, write_report

__all__ = ["run", "analyze", "validate_report", "write_report", "GapAnalysisError", "SourceError", "ReportError"]

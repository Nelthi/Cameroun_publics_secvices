"""Enchaîne lecture des sources -> analyse -> écriture du rapport."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .analyzer import DEFAULT_SIMILARITY, analyze
from .errors import GapAnalysisError, SourceError
from .models import AuditData, EvalData
from .readers import parse_timestamp, read_audit_db, read_eval_report, read_gaps_api, read_questions
from .report import write_report

DEFAULT_OUT = Path("data/reports/gap_report.json")
DEFAULT_EVAL_REPORT = Path("data/reports/eval_report.json")
DEFAULT_QUESTIONS = Path("data/eval/questions.json")
AUDIT_DB_CANDIDATES = (Path("data/audit.db"), Path("data/metadata/audit.db"), Path("audit.db"))
SOURCES = ("auto", "audit", "api")


def parse_since(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = parse_timestamp(value)
    if parsed is None:
        raise GapAnalysisError(f"--since '{value}' n'est pas une date ISO 8601 (ex. 2026-11-01 ou 2026-11-01T08:00:00)")
    return parsed


def load_audit(audit_db: str | Path | None, api_url: str | None, source: str, since: datetime | None,
               warnings: list[str]) -> AuditData | None:
    if source not in SOURCES:
        raise GapAnalysisError(f"source '{source}' inconnue (valeurs : {', '.join(SOURCES)})")
    if source == "api":
        if not api_url:
            raise SourceError("--source api demande --api-url")
        return read_gaps_api(api_url, since)

    db_path = Path(audit_db) if audit_db else next((p for p in AUDIT_DB_CANDIDATES if p.is_file()), None)
    if db_path is not None:
        try:
            return read_audit_db(db_path, since)
        except SourceError as exc:
            if source == "audit" or not api_url:
                raise
            warnings.append(f"audit.db inutilisable ({exc}) : repli sur GET /gaps")
            return read_gaps_api(api_url, since)
    if source == "audit":
        raise SourceError("audit.db introuvable (cherché : " + ", ".join(map(str, AUDIT_DB_CANDIDATES)) + ")")
    if api_url:
        return read_gaps_api(api_url, since)
    warnings.append("aucune source d'audit (audit.db introuvable, pas d'--api-url) : seuls les échecs d'évaluation sont analysés")
    return None


def load_eval(eval_report: str | Path | None, warnings: list[str]) -> EvalData | None:
    if eval_report is not None:  # chemin donné explicitement : il doit exister
        return read_eval_report(eval_report)
    if DEFAULT_EVAL_REPORT.is_file():
        return read_eval_report(DEFAULT_EVAL_REPORT)
    warnings.append(f"{DEFAULT_EVAL_REPORT} absent (T1 pas encore lancée ?) : seules les lacunes de l'audit sont analysées")
    return None


def run(*, audit_db=None, api_url=None, source: str = "auto", eval_report=None, questions=None,
        out: str | Path | None = DEFAULT_OUT, since: str | None = None,
        similarity: float = DEFAULT_SIMILARITY, count_unexpected: bool = False,
        now: datetime | None = None) -> tuple[dict, Path | None]:
    """Retourne (rapport, chemin écrit). `out=None` : rapport calculé mais non écrit."""
    if not 0.0 < similarity <= 1.0:
        raise GapAnalysisError("--similarity doit être dans ]0, 1]")
    since_dt = parse_since(since)
    warnings: list[str] = []
    audit = load_audit(audit_db, api_url, source, since_dt, warnings)
    eval_data = load_eval(eval_report, warnings)
    if audit is None and eval_data is None:
        raise SourceError("aucune source exploitable : fournissez audit.db (ou --api-url) et/ou eval_report.json")
    questions_path = questions if questions is not None else (DEFAULT_QUESTIONS if DEFAULT_QUESTIONS.is_file() else None)
    report = analyze(
        audit, eval_data, read_questions(questions_path), threshold=similarity,
        count_unexpected=count_unexpected, now=now, warnings=warnings,
        parameters={"since": since_dt.isoformat() if since_dt else None, "similarity": similarity,
                    "count_unexpected_answers": count_unexpected, "source": source})
    return report, (write_report(report, out) if out is not None else None)

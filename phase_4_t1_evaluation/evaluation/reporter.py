"""Écriture des rapports eval_report.json / eval_report.csv.

Jamais d'écrasement silencieux : les fichiers portent le run_id.
Si un fichier cible existe déjà, lève ReportWriteError sauf force=True.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from .exceptions import ReportWriteError
from .models import EvalReport

_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def validate_run_id(run_id: str) -> str:
    cleaned = (run_id or "").strip()
    if not cleaned or not _SAFE_RUN_ID.fullmatch(cleaned):
        raise ReportWriteError(
            "run_id invalide : utiliser uniquement lettres, chiffres, "
            "'.', '_' ou '-' (anti path traversal)."
        )
    return cleaned


def report_paths(reports_dir: str | Path, run_id: str) -> tuple[Path, Path]:
    safe_id = validate_run_id(run_id)
    root = Path(reports_dir)
    json_path = root / f"eval_report_{safe_id}.json"
    csv_path = root / f"eval_report_{safe_id}.csv"
    return json_path, csv_path


def _ensure_parent(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ReportWriteError(f"Impossible de créer le dossier rapports : {exc}") from exc


def _assert_not_exists(path: Path, *, force: bool) -> None:
    if path.exists() and not force:
        raise ReportWriteError(
            f"Le rapport existe déjà : {path}. "
            "Changez run_id ou passez force=True explicitement."
        )


def write_json_report(
    report: EvalReport,
    reports_dir: str | Path,
    *,
    force: bool = False,
) -> Path:
    json_path, _ = report_paths(reports_dir, report.run_id)
    _ensure_parent(json_path)
    _assert_not_exists(json_path, force=force)
    try:
        json_path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise ReportWriteError(f"Écriture JSON impossible : {exc}") from exc
    return json_path


def write_csv_report(
    report: EvalReport,
    reports_dir: str | Path,
    *,
    force: bool = False,
) -> Path:
    """CSV : une ligne résumé + une ligne par failure."""
    _, csv_path = report_paths(reports_dir, report.run_id)
    _ensure_parent(csv_path)
    _assert_not_exists(csv_path, force=force)

    metrics = report.metrics
    try:
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "row_type",
                    "run_id",
                    "n_questions",
                    "source_hit_rate",
                    "correct_refusal_rate",
                    "avg_duration_ms",
                    "question_id",
                    "request_id",
                    "expected_json",
                    "got_json",
                ]
            )
            writer.writerow(
                [
                    "summary",
                    report.run_id,
                    report.n_questions,
                    metrics.source_hit_rate,
                    metrics.correct_refusal_rate,
                    metrics.avg_duration_ms,
                    "",
                    "",
                    "",
                    "",
                ]
            )
            for failure in report.failures:
                writer.writerow(
                    [
                        "failure",
                        report.run_id,
                        report.n_questions,
                        "",
                        "",
                        "",
                        failure.question_id,
                        failure.request_id,
                        json.dumps(failure.expected, ensure_ascii=False),
                        json.dumps(failure.got, ensure_ascii=False),
                    ]
                )
    except OSError as exc:
        raise ReportWriteError(f"Écriture CSV impossible : {exc}") from exc
    return csv_path


def write_reports(
    report: EvalReport,
    reports_dir: str | Path,
    *,
    force: bool = False,
) -> tuple[Path, Path]:
    """Écrit JSON puis CSV ; retourne les deux chemins."""
    json_path = write_json_report(report, reports_dir, force=force)
    csv_path = write_csv_report(report, reports_dir, force=force)
    return json_path, csv_path

"""Exécution complète du jeu de tests d'évaluation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .ask_client import AskClient, create_ask_client
from .comparator import ComparisonResult, compare_case
from .config import EvalConfig, load_config
from .exceptions import AskClientError
from .metrics import build_report
from .models import EvalReport, FailureRecord
from .questions_loader import load_questions_file
from .reporter import write_reports


def make_run_id(prefix: str = "run") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{stamp}"


def run_evaluation(
    questions_path: str | Path,
    reports_dir: str | Path,
    *,
    run_id: Optional[str] = None,
    config: Optional[EvalConfig] = None,
    client: Optional[AskClient] = None,
    force: bool = False,
) -> EvalReport:
    """Charge les questions, appelle /ask, compare, écrit les rapports."""
    cfg = config or load_config()
    ask_client = client or create_ask_client(cfg)
    cases = load_questions_file(questions_path)
    active_run_id = run_id or make_run_id()

    results: list[ComparisonResult] = []
    exec_failures: list[FailureRecord] = []

    for case in cases:
        try:
            response = ask_client.ask(case)
        except AskClientError as exc:
            # Erreur réseau/HTTP ≠ refus correct.
            exec_failures.append(
                FailureRecord(
                    question_id=case.question_id,
                    expected=case.expected.to_dict(),
                    got={
                        "error_type": "ask_client_error",
                        "detail": str(exc),
                    },
                    request_id="REQ-ERROR",
                )
            )
            continue

        results.append(compare_case(case, response))

    report = build_report(
        run_id=active_run_id,
        n_questions=len(cases),
        results=results,
        extra_failures=exec_failures,
    )
    write_reports(report, reports_dir, force=force)
    return report

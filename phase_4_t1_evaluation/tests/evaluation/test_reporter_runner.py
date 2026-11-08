"""Tests Étape 5 — rapports JSON/CSV + runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.ask_client import MockAskClient
from evaluation.exceptions import ReportWriteError
from evaluation.models import (
    EvalMetrics,
    EvalReport,
    FailureRecord,
)
from evaluation.reporter import validate_run_id, write_reports
from evaluation.runner import run_evaluation


def test_validate_run_id_rejects_path_traversal() -> None:
    with pytest.raises(ReportWriteError):
        validate_run_id("../secret")


def test_write_reports_creates_json_and_csv(tmp_path: Path) -> None:
    report = EvalReport(
        run_id="run_demo",
        n_questions=1,
        metrics=EvalMetrics(1.0, 1.0, 12.0),
        failures=(
            FailureRecord(
                question_id="Q001",
                expected={"refused": False},
                got={"refused": True},
                request_id="REQ-1",
            ),
        ),
    )
    json_path, csv_path = write_reports(report, tmp_path)
    assert json_path.name == "eval_report_run_demo.json"
    assert csv_path.name == "eval_report_run_demo.csv"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert set(payload.keys()) == {
        "run_id",
        "n_questions",
        "metrics",
        "failures",
    }
    csv_text = csv_path.read_text(encoding="utf-8")
    assert "source_hit_rate" in csv_text
    assert "Q001" in csv_text


def test_write_reports_no_silent_overwrite(tmp_path: Path) -> None:
    report = EvalReport(
        run_id="run_same",
        n_questions=0,
        metrics=EvalMetrics(0.0, 0.0, 0.0),
        failures=(),
    )
    write_reports(report, tmp_path)
    with pytest.raises(ReportWriteError):
        write_reports(report, tmp_path)
    # force explicite autorisé
    write_reports(report, tmp_path, force=True)


def test_runner_with_mock_and_dataset(tmp_path: Path) -> None:
    questions = Path(__file__).resolve().parents[2] / "data" / "questions.json"
    reports_dir = tmp_path / "reports"
    report = run_evaluation(
        questions_path=questions,
        reports_dir=reports_dir,
        run_id="run_mock_full",
        client=MockAskClient(),
    )
    assert report.n_questions == 25
    assert (reports_dir / "eval_report_run_mock_full.json").is_file()
    assert (reports_dir / "eval_report_run_mock_full.csv").is_file()
    # En mock aligné sur expected, on s'attend à un bon taux
    assert report.metrics.source_hit_rate == 1.0
    assert report.metrics.correct_refusal_rate == 1.0

"""Phase 4 — T1 Jeu de test et Évaluation."""

from .ask_client import (
    AskClient,
    HttpAskClient,
    MockAskClient,
    create_ask_client,
    parse_ask_response,
)
from .comparator import ComparisonResult, compare_case, has_source_hit
from .config import EvalConfig, load_config
from .exceptions import (
    AskClientError,
    EvaluationError,
    QuestionsValidationError,
    ReportWriteError,
)
from .metrics import build_report, compute_metrics
from .models import (
    AskResponse,
    EvalMetrics,
    EvalReport,
    ExpectedResult,
    FailureRecord,
    QuestionCase,
    SourceRef,
)
from .questions_loader import load_questions_file, parse_questions_payload
from .reporter import write_csv_report, write_json_report, write_reports
from .runner import make_run_id, run_evaluation

__version__ = "0.6.0"

__all__ = [
    "AskClient",
    "AskClientError",
    "AskResponse",
    "ComparisonResult",
    "EvalConfig",
    "EvalMetrics",
    "EvalReport",
    "EvaluationError",
    "ExpectedResult",
    "FailureRecord",
    "HttpAskClient",
    "MockAskClient",
    "QuestionCase",
    "QuestionsValidationError",
    "ReportWriteError",
    "SourceRef",
    "build_report",
    "compare_case",
    "compute_metrics",
    "create_ask_client",
    "has_source_hit",
    "load_config",
    "load_questions_file",
    "make_run_id",
    "parse_ask_response",
    "parse_questions_payload",
    "run_evaluation",
    "write_csv_report",
    "write_json_report",
    "write_reports",
]

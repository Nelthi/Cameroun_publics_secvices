"""Chargement et validation de questions.json (structure seule — étape 1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .exceptions import QuestionsValidationError
from .models import ExpectedResult, QuestionCase, SourceRef

REQUIRED_QUESTION_FIELDS = ("question_id", "question", "language", "expected")
REQUIRED_EXPECTED_FIELDS = ("refused",)


def _require_dict(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise QuestionsValidationError(f"{context} doit être un objet JSON.")
    return value


def _require_non_empty_str(payload: dict[str, Any], field: str, context: str) -> str:
    if field not in payload:
        raise QuestionsValidationError(f"{context}: champ manquant '{field}'.")
    value = payload[field]
    if not isinstance(value, str) or not value.strip():
        raise QuestionsValidationError(
            f"{context}: '{field}' doit être une chaîne non vide."
        )
    return value.strip()


def _parse_source(raw: Any, context: str) -> SourceRef:
    data = _require_dict(raw, context)
    document_id = _require_non_empty_str(data, "document_id", context)

    chunk_id = data.get("chunk_id")
    if chunk_id is not None and (
        not isinstance(chunk_id, str) or not chunk_id.strip()
    ):
        raise QuestionsValidationError(
            f"{context}: chunk_id doit être une chaîne non vide si présent."
        )

    source_page = data.get("source_page")
    if source_page is not None and (
        not isinstance(source_page, int) or isinstance(source_page, bool)
    ):
        raise QuestionsValidationError(
            f"{context}: source_page doit être un entier si présent."
        )

    unexpected = set(data) - {"document_id", "chunk_id", "source_page"}
    if unexpected:
        raise QuestionsValidationError(
            f"{context}: champs source non autorisés : "
            + ", ".join(sorted(unexpected))
        )

    return SourceRef(
        document_id=document_id,
        chunk_id=chunk_id.strip() if isinstance(chunk_id, str) else None,
        source_page=source_page,
    )


def _parse_expected(raw: Any, context: str) -> ExpectedResult:
    data = _require_dict(raw, context)
    for field_name in REQUIRED_EXPECTED_FIELDS:
        if field_name not in data:
            raise QuestionsValidationError(
                f"{context}: champ manquant '{field_name}'."
            )

    refused = data["refused"]
    if not isinstance(refused, bool):
        raise QuestionsValidationError(f"{context}: 'refused' doit être un booléen.")

    sources_raw = data.get("sources", [])
    if not isinstance(sources_raw, list):
        raise QuestionsValidationError(f"{context}: 'sources' doit être une liste.")

    sources = tuple(
        _parse_source(item, f"{context}.sources[{index}]")
        for index, item in enumerate(sources_raw)
    )

    unexpected = set(data) - {"refused", "sources"}
    if unexpected:
        raise QuestionsValidationError(
            f"{context}: champs expected non autorisés : "
            + ", ".join(sorted(unexpected))
        )

    if refused and sources:
        raise QuestionsValidationError(
            f"{context}: une question refusée ne doit pas attendre de sources."
        )

    return ExpectedResult(refused=refused, sources=sources)


def parse_question_case(raw: Any, index: int) -> QuestionCase:
    """Valide et convertit un élément du tableau questions."""
    context = f"questions[{index}]"
    data = _require_dict(raw, context)

    for field_name in REQUIRED_QUESTION_FIELDS:
        if field_name not in data:
            raise QuestionsValidationError(
                f"{context}: champ manquant '{field_name}'."
            )

    question_id = _require_non_empty_str(data, "question_id", context)
    question = _require_non_empty_str(data, "question", context)
    language = _require_non_empty_str(data, "language", context)
    expected = _parse_expected(data["expected"], f"{context}.expected")

    unexpected = set(data) - set(REQUIRED_QUESTION_FIELDS)
    if unexpected:
        raise QuestionsValidationError(
            f"{context}: champs non autorisés : " + ", ".join(sorted(unexpected))
        )

    return QuestionCase(
        question_id=question_id,
        question=question,
        language=language,
        expected=expected,
    )


def parse_questions_payload(payload: Any) -> list[QuestionCase]:
    """Valide le document racine questions.json."""
    data = _require_dict(payload, "racine questions.json")
    if "questions" not in data:
        raise QuestionsValidationError("Champ racine manquant : 'questions'.")

    unexpected = set(data) - {"questions"}
    if unexpected:
        raise QuestionsValidationError(
            "Champs racine non autorisés : " + ", ".join(sorted(unexpected))
        )

    items = data["questions"]
    if not isinstance(items, list) or not items:
        raise QuestionsValidationError(
            "'questions' doit être une liste non vide."
        )

    cases = [parse_question_case(item, index) for index, item in enumerate(items)]

    seen_ids: set[str] = set()
    for case in cases:
        if case.question_id in seen_ids:
            raise QuestionsValidationError(
                f"question_id dupliqué : {case.question_id}"
            )
        seen_ids.add(case.question_id)

    return cases


def load_questions_file(path: str | Path) -> list[QuestionCase]:
    """Charge un fichier JSON et valide sa structure."""
    file_path = Path(path)
    if not file_path.is_file():
        raise QuestionsValidationError(f"Fichier introuvable : {file_path}")

    # Empêche les chemins exotiques d'échapper trop facilement (usage local).
    try:
        resolved = file_path.resolve()
    except OSError as exc:
        raise QuestionsValidationError(f"Chemin illisible : {exc}") from exc

    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        raise QuestionsValidationError(f"Lecture impossible : {exc}") from exc

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise QuestionsValidationError(f"JSON invalide : {exc}") from exc

    return parse_questions_payload(payload)

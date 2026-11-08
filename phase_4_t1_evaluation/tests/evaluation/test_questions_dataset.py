"""Tests Étape 2 — jeu de questions data/questions.json."""

from __future__ import annotations

from pathlib import Path

from evaluation.questions_loader import load_questions_file

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "questions.json"


def test_questions_file_loads_and_is_valid() -> None:
    cases = load_questions_file(DATA_FILE)
    assert 20 <= len(cases) <= 30


def test_questions_cover_refusals_and_source_cases() -> None:
    cases = load_questions_file(DATA_FILE)
    refused = [case for case in cases if case.expected.refused]
    with_sources = [
        case for case in cases if not case.expected.refused and case.expected.sources
    ]
    assert len(refused) >= 5
    assert len(with_sources) >= 10


def test_no_personal_data_markers_in_questions() -> None:
    """Garde-fou simple : pas de patterns typiques de données personnelles."""
    text = DATA_FILE.read_text(encoding="utf-8").lower()
    forbidden = ["@gmail.com", "numéro de cni réel", "password", "motdepasse"]
    for token in forbidden:
        assert token not in text


def test_question_ids_are_unique_and_ordered_prefix() -> None:
    cases = load_questions_file(DATA_FILE)
    ids = [case.question_id for case in cases]
    assert len(ids) == len(set(ids))
    assert all(question_id.startswith("Q") for question_id in ids)

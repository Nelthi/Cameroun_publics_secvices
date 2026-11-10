"""Tests Étape 1 — question_cleaner."""

from __future__ import annotations

import pytest

from backend.orchestration.exceptions import InvalidRequestError
from backend.orchestration.question_cleaner import clean_question, fold_accents


def test_clean_lowercases_and_strips() -> None:
    assert clean_question("  Comment Obtenir Une CNI ?  ") == (
        "comment obtenir une cni ?"
    )


def test_clean_preserves_accents_in_nfc() -> None:
    result = clean_question("Carte nationale d'identité")
    assert "identité" in result
    assert result == "carte nationale d'identité"


def test_clean_collapses_whitespace_and_newlines() -> None:
    raw = "Comment\tobtenir\nune   carte ?"
    assert clean_question(raw) == "comment obtenir une carte ?"


def test_clean_removes_control_and_strange_symbols() -> None:
    raw = "Aide*** pour ##CNI\x00!!!"
    assert clean_question(raw) == "aide pour cni!!!"


def test_clean_keeps_useful_punctuation() -> None:
    assert clean_question("Quel est le délai ?") == "quel est le délai ?"


def test_fold_accents_removes_diacritics() -> None:
    assert fold_accents("identité juridique") == "identite juridique"
    assert fold_accents("Éducation") == "Education"


def test_clean_then_fold_for_keyword_matching() -> None:
    cleaned = clean_question("Obtenir une carte d'identité")
    folded = fold_accents(cleaned)
    assert folded == "obtenir une carte d'identite"


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "\n\t", "****", "\u200b\u200b"],
)
def test_clean_rejects_empty_after_cleaning(raw: str) -> None:
    with pytest.raises(InvalidRequestError):
        clean_question(raw)


def test_clean_rejects_non_string() -> None:
    with pytest.raises(InvalidRequestError):
        clean_question(123)  # type: ignore[arg-type]

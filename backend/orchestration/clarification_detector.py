"""Détection des questions ambiguës ou incomplètes (T1 Phase 3)."""

from __future__ import annotations

from typing import Optional, Sequence

from .config import (
    CLARIFICATION_MIN_TOKENS,
    UNKNOWN_DOMAIN,
    VAGUE_QUESTION_PATTERNS,
)
from .exceptions import InvalidRequestError
from .question_cleaner import clean_question, fold_accents


def _normalize(text: str) -> str:
    return fold_accents(clean_question(text))


def needs_clarification(
    question: str,
    *,
    intent: Optional[str] = None,
    domain: Optional[str] = None,
    vague_patterns: Sequence[str] | None = None,
    min_tokens: int = CLARIFICATION_MIN_TOKENS,
) -> bool:
    """Indique si la question est trop vague pour un routage utile.

    Règles déterministes :
    1. Si intent == hors_sujet → False
       (hors sujet ≠ ambigu : on ne demande pas de clarification métier).
    2. Si la question normalisée égale / contient un motif vague exact
       (souvent la question entière) → True.
    3. Si la question est très courte (< min_tokens) et domain unknown → True.
    4. Sinon → False.

    Les paramètres intent/domain sont fournis par l'orchestrateur (étape 6).
    """
    if not isinstance(question, str) or not question.strip():
        raise InvalidRequestError("question vide pour la détection de clarification.")

    if intent == "hors_sujet":
        return False

    normalized = _normalize(question)
    patterns = vague_patterns if vague_patterns is not None else VAGUE_QUESTION_PATTERNS
    folded_patterns = tuple(fold_accents(p.lower()) for p in patterns)

    # Motif vague couvrant toute la question (ex. « comment faire ? »).
    if normalized in folded_patterns:
        return True
    # Motif vague dominant : question courte égale au motif + ponctuation déjà retirée.
    for pattern in folded_patterns:
        if normalized == pattern or normalized.rstrip("?.!;") == pattern:
            return True

    tokens = [tok for tok in normalized.replace("?", " ").split() if tok]
    domain_value = domain or UNKNOWN_DOMAIN
    if len(tokens) < min_tokens and domain_value == UNKNOWN_DOMAIN:
        return True

    return False

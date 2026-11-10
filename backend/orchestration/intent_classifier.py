"""Classification d'intention par mots-clés et règles déterministes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .config import INTENT_KEYWORDS, INTENT_PRIORITY
from .exceptions import InvalidRequestError
from .models import ALLOWED_INTENTS, IntentName
from .question_cleaner import clean_question, fold_accents


@dataclass(frozen=True)
class IntentScore:
    intent: IntentName
    score: int
    matched_keywords: tuple[str, ...]


def _normalize_for_match(text: str) -> str:
    """Nettoie + retire les accents pour un matching robuste."""
    return fold_accents(clean_question(text))


def score_intents(
    question: str,
    *,
    keywords: Mapping[str, Sequence[str]] | None = None,
) -> list[IntentScore]:
    """Calcule un score par intention (nombre de mots-clés trouvés)."""
    if not isinstance(question, str) or not question.strip():
        raise InvalidRequestError("question vide pour la classification.")

    normalized = _normalize_for_match(question)
    source = keywords if keywords is not None else INTENT_KEYWORDS
    scores: list[IntentScore] = []

    for intent, patterns in source.items():
        if intent not in ALLOWED_INTENTS:
            continue
        matched = [
            pattern
            for pattern in patterns
            if fold_accents(pattern.lower()) in normalized
        ]
        scores.append(
            IntentScore(
                intent=intent,  # type: ignore[arg-type]
                score=len(matched),
                matched_keywords=tuple(matched),
            )
        )

    return scores


def classify_intent(
    question: str,
    *,
    keywords: Mapping[str, Sequence[str]] | None = None,
    priority: Sequence[str] | None = None,
) -> IntentName:
    """Retourne une seule intention selon priorité + scores.

    Règles :
    - Score = nombre de motifs trouvés dans la question normalisée.
    - Parmi les intentions avec score > 0, INTENT_PRIORITY décide d'abord
      (donnees_personnelles > juridique > procedure > accueil > hors_sujet).
    - À priorité égale, le score le plus élevé l'emporte.
    - Si tous les scores sont nuls → hors_sujet.
    """
    scores = score_intents(question, keywords=keywords)
    order = tuple(priority) if priority is not None else INTENT_PRIORITY
    priority_index = {name: idx for idx, name in enumerate(order)}

    positive = [item for item in scores if item.score > 0]
    if not positive:
        return "hors_sujet"

    def sort_key(item: IntentScore) -> tuple[int, int]:
        # priorité croissante (index plus petit = prioritaire), puis score décroissant
        return (priority_index.get(item.intent, 999), -item.score)

    positive.sort(key=sort_key)
    return positive[0].intent

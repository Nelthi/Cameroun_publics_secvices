"""Nettoyage déterministe des questions citoyennes (T1 Phase 3).

Objectifs :
- Uniformiser la casse pour la classification par mots-clés.
- Normaliser les accents / formes Unicode (NFC).
- Réduire les espaces et caractères de contrôle.
- Conserver la ponctuation utile (?, !, ., ', -).

Ce module ne classifie pas : il prépare uniquement le texte.
"""

from __future__ import annotations

import re
import unicodedata

from .exceptions import InvalidRequestError

# Remplace tout blanc (espace, tab, newline, etc.) par un espace simple.
_WHITESPACE_RE = re.compile(r"\s+")
# Conserve lettres (y compris accentuées), chiffres et ponctuation utile.
_ALLOWED_CHARS_RE = re.compile(
    r"[^0-9A-Za-zÀ-ÖØ-öø-ÿĀ-žḀ-ỿ'’\-.,;:!?()/\s]+",
    flags=re.UNICODE,
)


def clean_question(question: str) -> str:
    """Nettoie une question pour les étapes de classification.

    Raises:
        InvalidRequestError: si la question est vide après nettoyage.
    """
    if not isinstance(question, str):
        raise InvalidRequestError("question doit être une chaîne.")

    # Forme canonique Unicode (é reste é, pas e + accent combiné).
    text = unicodedata.normalize("NFC", question)
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    text = "".join(
        char for char in text if unicodedata.category(char)[0] != "C" or char in "\n\t "
    )
    text = _ALLOWED_CHARS_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    text = text.lower()

    if not text:
        raise InvalidRequestError("question vide après nettoyage.")

    return text


def fold_accents(text: str) -> str:
    """Variante sans diacritiques, utile pour matcher des mots-clés.

    Exemple : « identité » → « identite ».
    Ne remplace pas clean_question : on l'utilise en complément.
    """
    if not isinstance(text, str):
        raise InvalidRequestError("text doit être une chaîne.")
    decomposed = unicodedata.normalize("NFD", text)
    without_marks = "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    )
    return unicodedata.normalize("NFC", without_marks)

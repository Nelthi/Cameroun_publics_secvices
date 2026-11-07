"""Masquage des données personnelles dans la question avant tout envoi au LLM.

Le projet promet « aucune donnée stockée » : un numéro de téléphone ou de CNI tapé par
le citoyen ne doit jamais partir vers un LLM externe. Seule la question MASQUÉE est
utilisée pour la recherche et pour le prompt.
"""
from __future__ import annotations

import re

MASK = "[NUMERO_MASQUE]"

_PATTERNS = (
    # Téléphone camerounais avec indicatif : +237 6 55 12 34 56, 00237655123456...
    re.compile(r"(?<!\d)(?:\+|00)\s?237[\s.\-]?\d(?:[\s.\-]?\d){7,8}(?!\d)"),
    # Mobile camerounais sans indicatif : 6 55 12 34 56, 655-123-456...
    re.compile(r"(?<!\d)6(?:[\s.\-]?\d){8}(?!\d)"),
    # Toute suite de 8 chiffres ou plus (numéro de CNI, de dossier, de compte...).
    re.compile(r"(?<!\d)\d{8,}(?!\d)"),
)

_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
EMAIL_MASK = "[EMAIL_MASQUE]"


def mask_sensitive(text: str) -> tuple[str, bool]:
    """Renvoie (texte masqué, True si quelque chose a été masqué)."""
    masked = text
    for pattern in _PATTERNS:
        masked = pattern.sub(MASK, masked)
    masked = _EMAIL.sub(EMAIL_MASK, masked)
    return masked, masked != text

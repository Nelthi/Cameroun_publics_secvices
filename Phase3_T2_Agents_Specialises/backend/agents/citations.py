"""Gestion des renvois [n] dans les brouillons.

Le LLM reçoit des passages numérotés [1]..[N] et cite ses sources avec ces numéros.
Après sa réponse, on :
  1. normalises les groupes  « [1, 2] » -> « [1][2] » ;
  2. supprime les renvois invalides (numéro hors de 1..N) et les signale ;
  3. renumérote les renvois restants dans l'ordre d'apparition, de façon que
     le renvoi [k] du texte désigne exactement citations[k-1] dans la sortie.
"""
from __future__ import annotations

import re

_GROUP_RE = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)+)\]")
_SINGLE_RE = re.compile(r"\[(\d+)\]")
# Renvoi précédé de ses espaces : supprimer un renvoi invalide emporte aussi l'espace qui le précède
# (sans toucher aux espaces avant « : ; ? ! » qui font partie de la typographie française).
_WITH_SPACE_RE = re.compile(r"([ \t]*)\[(\d+)\]")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_DUPLICATE_RE = re.compile(r"(\[\d+\])(?:\s*\1)+")


def expand_groups(text: str) -> str:
    """« [1, 2] » ou « [1;2] » -> « [1][2] »."""
    def repl(match: re.Match) -> str:
        numbers = re.split(r"\s*[,;]\s*", match.group(1))
        return "".join(f"[{n}]" for n in numbers)

    return _GROUP_RE.sub(repl, text)


def extract_indices(text: str) -> list[int]:
    """Numéros de renvoi présents dans le texte (ordre d'apparition, avec répétitions)."""
    return [int(n) for n in _SINGLE_RE.findall(expand_groups(text))]


def remap_citations(text: str, n_passages: int) -> tuple[str, list[int], list[int]]:
    """Valide et renumérote les renvois.

    Retourne (texte_nettoyé, utilisés, invalides) où :
      - utilisés  = numéros ORIGINAUX (1..n_passages) dans l'ordre de première apparition ;
                    le renvoi [k] du texte nettoyé correspond à utilisés[k-1] ;
      - invalides = numéros hors de 1..n_passages supprimés du texte (sans doublon).
    """
    text = expand_groups(text)
    mapping: dict[int, int] = {}
    used: list[int] = []
    invalid: list[int] = []

    def repl(match: re.Match) -> str:
        original = int(match.group(2))
        if not 1 <= original <= n_passages:
            if original not in invalid:
                invalid.append(original)
            return ""
        if original not in mapping:
            used.append(original)
            mapping[original] = len(used)
        return f"{match.group(1)}[{mapping[original]}]"

    cleaned = _WITH_SPACE_RE.sub(repl, text)
    cleaned = _DUPLICATE_RE.sub(r"\1", cleaned)
    cleaned = _MULTI_SPACE_RE.sub(" ", cleaned)
    return cleaned.strip(), used, invalid

"""Classement des échecs de l'évaluation (T1) : lesquels révèlent un document manquant ?

Rappel du contrat de T1 : failures = [{question_id, expected, got, request_id}], où `expected`
vaut « refused » ou une source attendue (document + page), et `got` est le statut obtenu
(« approved », « partial », « refused »).

| attendu        | obtenu              | type              | lacune de la base ?                     |
|----------------|---------------------|-------------------|-----------------------------------------|
| une source     | refused             | source_missing    | oui : rien trouvé dans la base          |
| une source     | partial             | partial_answer    | oui : réponse incomplète                |
| une source     | approved (autre doc)| wrong_source      | oui : la bonne source manque ou est mal classée |
| refused        | approved / partial  | unexpected_answer | non : problème de garde-fous (T3 Phase 3), pas de document à chercher |
"""
from __future__ import annotations

from .text import fold

REFUSALS = frozenset({"refused", "refuse", "refus"})
GAP_TYPES = ("source_missing", "partial_answer", "wrong_source")
NON_GAP_TYPE = "unexpected_answer"


def _status(value) -> str:
    if isinstance(value, dict):
        value = value.get("status") or value.get("result")
    return fold(value) if isinstance(value, str) else ""


def expects_refusal(expected) -> bool:
    return _status(expected) in REFUSALS


def classify_failure(expected, got) -> str | None:
    """Type d'échec, ou None si ce n'en est pas un (attendu vide, ou refus correct)."""
    if expected in (None, "", [], {}):
        return None
    got_status = _status(got)
    if expects_refusal(expected):
        return None if got_status in REFUSALS else NON_GAP_TYPE
    if got_status in REFUSALS:
        return "source_missing"
    if got_status == "partial":
        return "partial_answer"
    return "wrong_source"

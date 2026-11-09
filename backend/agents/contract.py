"""Contrat de sortie de T2 et validation (même esprit que chunking/validate.py).

Brouillon produit par un agent :
{
  "request_id": "REQ-20261106-0001",
  "agent": "procedure",
  "answer_draft": "Pour la CNI, il faut ... [1][2]",
  "citations": [{"chunk_id": "DOC-...-C001", "document_id": "DOC-...", "source_page": 1}],
  "retrieval": {"top_score": 0.71, "n_chunks": 4, "passages": [...]},   # passages : ajout facultatif
  "meta": {...}                                                         # ajout facultatif
}
Les clés du guide (request_id, agent, answer_draft, citations, retrieval.top_score,
retrieval.n_chunks) sont inchangées. `retrieval.passages` et `meta` sont des AJOUTS : un
consommateur qui ne les connaît pas peut les ignorer.
"""
from __future__ import annotations

from .citations import extract_indices

CITATION_FIELDS = ("chunk_id", "document_id", "source_page")
PASSAGE_FIELDS = ("chunk_id", "document_id", "source_page", "text", "score")


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_draft(draft) -> list[str]:
    """Liste des erreurs de contrat (liste vide = brouillon conforme)."""
    if not isinstance(draft, dict):
        return ["le brouillon n'est pas un objet JSON"]
    errors: list[str] = []

    for key in ("request_id", "agent", "answer_draft"):
        if not isinstance(draft.get(key), str) or not draft[key].strip():
            errors.append(f"'{key}' manquant ou n'est pas un texte non vide")

    citations = draft.get("citations")
    if not isinstance(citations, list):
        errors.append("'citations' manquant ou n'est pas une liste")
        citations = []
    for i, cit in enumerate(citations):
        if not isinstance(cit, dict):
            errors.append(f"citations[{i}] n'est pas un objet")
            continue
        for field in CITATION_FIELDS:
            if field not in cit:
                errors.append(f"citations[{i}] sans champ '{field}'")
        for field in ("chunk_id", "document_id"):
            if field in cit and not (isinstance(cit[field], str) and cit[field]):
                errors.append(f"citations[{i}].{field} doit être un texte non vide")
        if "source_page" in cit and not _is_int(cit["source_page"]):
            errors.append(f"citations[{i}].source_page doit être un entier")

    retrieval = draft.get("retrieval")
    passages = None
    if not isinstance(retrieval, dict):
        errors.append("'retrieval' manquant ou n'est pas un objet")
    else:
        score = retrieval.get("top_score")
        if not _is_number(score) or not 0.0 <= score <= 1.0:
            errors.append("retrieval.top_score doit être un nombre entre 0 et 1")
        if not _is_int(retrieval.get("n_chunks")) or retrieval["n_chunks"] < 0:
            errors.append("retrieval.n_chunks doit être un entier >= 0")
        passages = retrieval.get("passages")
        if passages is not None:
            if not isinstance(passages, list):
                errors.append("retrieval.passages doit être une liste")
                passages = None
            else:
                for i, passage in enumerate(passages):
                    missing = [f for f in PASSAGE_FIELDS if not isinstance(passage, dict) or f not in passage]
                    if missing:
                        errors.append(f"retrieval.passages[{i}] sans champ(s) {missing}")

    if isinstance(draft.get("answer_draft"), str):
        bad = sorted({n for n in extract_indices(draft["answer_draft"]) if not 1 <= n <= len(citations)})
        if bad:
            errors.append(f"renvois {bad} sans citation correspondante (il y a {len(citations)} citation(s))")

    if passages and not errors:
        known = {p["chunk_id"] for p in passages}
        for i, cit in enumerate(citations):
            if cit["chunk_id"] not in known:
                errors.append(f"citations[{i}] ({cit['chunk_id']}) absente des passages récupérés")

    if "meta" in draft and not isinstance(draft["meta"], dict):
        errors.append("'meta' doit être un objet")
    return errors

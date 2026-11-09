"""Fusion de plusieurs brouillons (1 à 3 agents) en UN brouillon au même contrat.

T3 reçoit « le brouillon de T2 » au singulier : quand T1 désigne plusieurs agents, cette
fonction les assemble, sans LLM. Les renvois [n] de chaque agent sont recalculés pour
désigner la liste de citations fusionnée (dédoublonnée par chunk_id).
"""
from __future__ import annotations

import re

from .citations import expand_groups
from .contract import validate_draft
from .exceptions import ContractError
from .messages import SECTION_LABEL, normalize_language


def _is_informative(draft: dict) -> bool:
    meta = draft.get("meta", {})
    return meta.get("kind") == "rag" and not meta.get("no_answer")


def merge_drafts(drafts: list[dict]) -> dict:
    if not drafts:
        raise ContractError("aucun brouillon à fusionner")
    for draft in drafts:
        errors = validate_draft(draft)
        if errors:
            raise ContractError(f"brouillon de l'agent {draft.get('agent') if isinstance(draft, dict) else '?'} invalide : "
                                + " ; ".join(errors))
    request_ids = {d["request_id"] for d in drafts}
    if len(request_ids) != 1:
        raise ContractError(f"request_id différents : {sorted(request_ids)}")

    agents = [d["agent"] for d in drafts]
    informative = [d for d in drafts if _is_informative(d)]
    if len(drafts) == 1 or not informative:
        # Un seul brouillon, ou aucun n'apporte d'information : on garde le premier, sans le dénaturer.
        chosen = next((d for d in drafts if d.get("meta", {}).get("kind") == "static"), drafts[0])
        merged = {**chosen, "meta": {**chosen.get("meta", {}), "agents": agents}}
        return merged

    language = normalize_language(informative[0]["meta"].get("language"))
    labels = SECTION_LABEL[language]
    citations: list[dict] = []
    index_by_chunk: dict[str, int] = {}
    passages_by_chunk: dict[str, dict] = {}
    sections: list[str] = []
    meta: dict = {"kind": "rag", "language": language, "no_answer": False, "agents": agents}

    for draft in informative:
        local_to_global: dict[int, int] = {}
        for local, cit in enumerate(draft["citations"], start=1):
            if cit["chunk_id"] not in index_by_chunk:
                citations.append(dict(cit))
                index_by_chunk[cit["chunk_id"]] = len(citations)
            local_to_global[local] = index_by_chunk[cit["chunk_id"]]
        text = re.sub(r"\[(\d+)\]", lambda m: f"[{local_to_global[int(m.group(1))]}]", expand_groups(draft["answer_draft"]))
        label = labels.get(draft["agent"], draft["agent"])
        sections.append(f"{label} :\n{text}")
        for passage in draft["retrieval"].get("passages", []):
            best = passages_by_chunk.get(passage["chunk_id"])
            if best is None or passage["score"] > best["score"]:
                passages_by_chunk[passage["chunk_id"]] = passage
        for key in ("admits_missing_info", "sensitive_data_masked", "question_truncated"):
            if draft["meta"].get(key):
                meta[key] = True
        invalid = draft["meta"].get("invalid_citations_removed")
        if invalid:
            meta.setdefault("invalid_citations_removed", [])
            meta["invalid_citations_removed"] = sorted(set(meta["invalid_citations_removed"]) | set(invalid))

    # Un agent qui n'a rien trouvé alors que d'autres répondent : la lacune reste signalée.
    if any(d.get("meta", {}).get("no_answer") or d.get("meta", {}).get("kind") == "error" for d in drafts):
        meta["admits_missing_info"] = True

    passages = sorted(passages_by_chunk.values(), key=lambda p: -p["score"])
    passages = [{**p, "rank": i} for i, p in enumerate(passages, start=1)]
    return {
        "request_id": drafts[0]["request_id"],
        "agent": "merged",
        "answer_draft": "\n\n".join(sections),
        "citations": citations,
        "retrieval": {
            "top_score": max(d["retrieval"]["top_score"] for d in informative),
            "n_chunks": len(passages),
            "passages": passages,
        },
        "meta": meta,
    }

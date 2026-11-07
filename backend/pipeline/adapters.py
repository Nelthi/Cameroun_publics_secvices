"""Adaptateurs entre les formats de T1, T2, T3 et T4."""
from __future__ import annotations


def t2_output_to_t3_input(processed: dict) -> dict:
    """Sortie T2 (content.segments) -> entrée T3 (document_id + pages[]).

    Les TXT/DOCX n'ont pas de numéro de page : ils sont rangés en page 1.
    """
    pages = [
        {"page_number": seg.get("page_number") or 1, "text": seg["text"]}
        for seg in processed["content"]["segments"]
    ]
    return {"document_id": processed["document_id"], "pages": pages}

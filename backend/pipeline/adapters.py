"""Adaptateurs entre les formats de T1, T2, T3 et T4."""
from __future__ import annotations

from pathlib import PurePosixPath


class T1RepositoryForT2:
    """Présente le registre SQLite de T1 sous la forme attendue par le
    DocumentProcessor de T2 (champ `metadata`, chemin relatif à data/)."""

    def __init__(self, t1_repository):
        self._repo = t1_repository

    def get(self, document_id):
        row = self._repo.get(document_id)
        if row is None:
            return None
        record = dict(row)
        stored = PurePosixPath(record["stored_path"].replace("\\", "/"))
        # T1 range sous "data/raw/..." ; T2 attend un chemin relatif à data/.
        if stored.parts and stored.parts[0] == "data":
            stored = PurePosixPath(*stored.parts[1:])
        record["stored_path"] = str(stored)
        record["metadata"] = {
            key: row.get(key)
            for key in ("title", "institution", "domain", "subdomain", "document_date")
        }
        return record


def t2_output_to_t3_input(processed: dict) -> dict:
    """Sortie T2 (content.segments) -> entrée T3 (document_id + pages[]).

    Les TXT/DOCX n'ont pas de numéro de page : ils sont rangés en page 1.
    """
    pages = [
        {"page_number": seg.get("page_number") or 1, "text": seg["text"]}
        for seg in processed["content"]["segments"]
    ]
    return {"document_id": processed["document_id"], "pages": pages}

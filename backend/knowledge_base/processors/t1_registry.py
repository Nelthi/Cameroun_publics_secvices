"""Lit le registre SQLite de T1 sous la forme attendue par le DocumentProcessor de T2.

Ajouté lors de la fusion : T2 lisait à l'origine un registre écrit par son propre
« collector » ; il lit maintenant celui de T1 (même fichier data/metadata/documents.sqlite3).
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Optional

from backend.knowledge_base.database.repository import DocumentRepository as T1Repository


class T1RepositoryForT2:
    def __init__(self, repository_or_path):
        if isinstance(repository_or_path, (str, Path)):
            repository_or_path = T1Repository(Path(repository_or_path))
        self._repo = repository_or_path

    @staticmethod
    def _convert(row: dict) -> dict:
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

    def get(self, document_id: str) -> Optional[dict]:
        row = self._repo.get(document_id)
        return None if row is None else self._convert(row)

    def list_documents(self, domain: Optional[str] = None) -> list:
        return [self._convert(r) for r in self._repo.list_documents(domain=domain)]

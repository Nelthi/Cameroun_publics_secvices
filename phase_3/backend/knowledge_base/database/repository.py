"""Persistance SQLite des documents ingérés (T1)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional


class DocumentRepository:
    """Registre des documents : métadonnées + chemins de fichiers."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    sha256 TEXT NOT NULL UNIQUE,
                    original_filename TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    upload_date TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    subdomain TEXT NOT NULL,
                    institution TEXT NOT NULL,
                    title TEXT NOT NULL,
                    document_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    file_format TEXT NOT NULL,
                    file_size INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_documents_domain
                ON documents(domain)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_documents_sha256
                ON documents(sha256)
                """
            )

    def exists_by_hash(self, sha256: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM documents WHERE sha256 = ?",
                (sha256,),
            ).fetchone()
        return row is not None

    def get_by_hash(self, sha256: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE sha256 = ?",
                (sha256,),
            ).fetchone()
        return dict(row) if row else None

    def get(self, document_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        return dict(row) if row else None

    def insert(self, record: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    document_id, sha256, original_filename, stored_path,
                    upload_date, domain, subdomain, institution, title,
                    document_date, status, file_format, file_size
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["document_id"],
                    record["sha256"],
                    record["original_filename"],
                    record["stored_path"],
                    record["upload_date"],
                    record["domain"],
                    record["subdomain"],
                    record["institution"],
                    record["title"],
                    record["document_date"],
                    record["status"],
                    record["file_format"],
                    record["file_size"],
                ),
            )

    def list_documents(
        self,
        domain: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if domain:
                rows = conn.execute(
                    """
                    SELECT * FROM documents
                    WHERE domain = ?
                    ORDER BY upload_date DESC
                    """,
                    (domain,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM documents ORDER BY upload_date DESC"
                ).fetchall()
        return [dict(row) for row in rows]

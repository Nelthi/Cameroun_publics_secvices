import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


class DocumentRepository:
    """SQLite persistence for document metadata and file references."""

    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    original_filename TEXT NOT NULL,
                    stored_filename TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    file_format TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    sha256 TEXT NOT NULL UNIQUE,
                    imported_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_domain
                ON documents(json_extract(metadata_json, '$.domain'))
            """)

    def exists_by_hash(self, sha256: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM documents WHERE sha256 = ?", (sha256,)
            ).fetchone()
            return row is not None

    def insert(self, record: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO documents (
                    document_id, original_filename, stored_filename,
                    stored_path, file_format, file_size, sha256,
                    imported_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record["document_id"], record["original_filename"],
                record["stored_filename"], record["stored_path"],
                record["file_format"], record["file_size"],
                record["sha256"], record["imported_at"],
                json.dumps(record["metadata"], ensure_ascii=False)
            ))

    def get(self, document_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE document_id = ?",
                (document_id,)
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_documents(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if domain:
                rows = conn.execute("""
                    SELECT * FROM documents
                    WHERE json_extract(metadata_json, '$.domain') = ?
                    ORDER BY imported_at DESC
                """, (domain,)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM documents ORDER BY imported_at DESC"
                ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    @staticmethod
    def _row_to_dict(row):
        result = dict(row)
        result["metadata"] = json.loads(result["metadata_json"])
        del result["metadata_json"]
        return result

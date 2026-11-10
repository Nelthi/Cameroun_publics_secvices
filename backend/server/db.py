"""Base SQLite de l'application (conversations, messages, journal des phases)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime

from .settings import data_root

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL, role TEXT NOT NULL,
    content TEXT NOT NULL, status TEXT, sources_json TEXT, request_id TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS phase_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, document_id TEXT NOT NULL, phase TEXT NOT NULL,
    mode TEXT, detail TEXT, created_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def connect():
    path = data_root() / "app.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

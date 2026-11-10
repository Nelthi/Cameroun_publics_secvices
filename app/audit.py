"""Journal d'audit SQLite : tables audit_log et gaps."""
import json
import re
import sqlite3
from contextlib import contextmanager

from .config import get_db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    request_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    question TEXT NOT NULL,
    routing_json TEXT,
    agent_outputs_json TEXT,
    validation_json TEXT,
    status TEXT NOT NULL,
    final_answer TEXT,
    duration_ms INTEGER,
    error TEXT
);
CREATE TABLE IF NOT EXISTS gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    reason TEXT,
    timestamp TEXT NOT NULL
);
"""

# Suite de 8 chiffres ou plus (séparés ou non par espace, point, tiret) :
# numéro de CNI, de téléphone... Les identifiants REQ-... ne sont pas touchés.
_LONG_NUMBER = re.compile(r"(?<![\w-])\d(?:[ .-]?\d){7,}(?![\w-])")


def mask_sensitive(text: str) -> str:
    return _LONG_NUMBER.sub("[NUMÉRO MASQUÉ]", text)


@contextmanager
def _connect():
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)  # crée les tables si elles n'existent pas
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def write_audit(record: dict, gaps: list) -> None:
    """Écrit une ligne d'audit + les lacunes, dans une seule transaction."""
    with _connect() as conn:
        conn.execute(
            """INSERT INTO audit_log (request_id, timestamp, question, routing_json,
               agent_outputs_json, validation_json, status, final_answer, duration_ms, error)
               VALUES (:request_id, :timestamp, :question, :routing_json,
               :agent_outputs_json, :validation_json, :status, :final_answer,
               :duration_ms, :error)""",
            record,
        )
        for gap in gaps:
            conn.execute(
                "INSERT INTO gaps (request_id, topic, reason, timestamp) VALUES (?, ?, ?, ?)",
                (record["request_id"], gap["topic"], gap.get("reason"), record["timestamp"]),
            )


def get_audit(request_id: str):
    """Ligne d'audit complète (colonnes JSON relues en objets), ou None."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM audit_log WHERE request_id = ?", (request_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        for col in ("routing_json", "agent_outputs_json", "validation_json"):
            data[col] = json.loads(data[col]) if data[col] else None
        data["gaps"] = [dict(g) for g in conn.execute(
            "SELECT topic, reason FROM gaps WHERE request_id = ?", (request_id,))]
        return data


def list_gaps():
    """Lacunes regroupées par sujet, les plus fréquentes d'abord."""
    with _connect() as conn:
        return [dict(r) for r in conn.execute(
            """SELECT topic, reason, COUNT(*) AS count, MAX(timestamp) AS last_seen
               FROM gaps GROUP BY topic, reason ORDER BY count DESC, last_seen DESC""")]

"""Lecture des sources : audit.db (SQLite), GET /gaps, eval_report.json, questions.json.

Le schéma exact de audit.db appartient à la Phase 3 (qu'on ne modifie pas). Les lecteurs détectent
donc les colonnes par leur nom (voir COLUMN_ALIASES : seul endroit à ajuster si le schéma diffère).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .errors import SourceError
from .models import AuditContext, AuditData, EvalData, Observation
from .text import clean_text

MAX_TOPIC_CHARS = 120
MAX_QUESTION_CHARS = 200

# Noms de colonnes acceptés (minuscules), par rôle. Le premier présent dans la table est utilisé.
COLUMN_ALIASES = {
    "topic": ("topic", "subject", "sujet", "gap_topic"),
    "reason": ("reason", "raison", "gap_reason"),
    "request_id": ("request_id", "req_id", "requestid"),
    "timestamp": ("created_at", "timestamp", "detected_at", "date", "ts", "created"),
    "domain": ("domain", "domaine"),
    "subdomain": ("subdomain", "sous_domaine"),
    "count": ("occurrences", "count", "nb_occurrences", "n", "total", "nb"),
    "question": ("question", "query", "text"),
    "routing": ("routing", "routage", "routing_plan", "route"),
}
GAPS_TABLE = "gaps"
LOG_TABLE = "audit_log"
API_LIST_KEYS = ("gaps", "items", "results", "data")


def parse_timestamp(value) -> datetime | None:
    """ISO 8601 (avec ou sans fuseau, « Z » accepté) ou epoch -> datetime naïf en UTC. None si illisible."""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return datetime.fromtimestamp(float(value), tz=timezone.utc).replace(tzinfo=None)
        text = str(value).strip()
        if text.replace(".", "", 1).isdigit():
            return datetime.fromtimestamp(float(text), tz=timezone.utc).replace(tzinfo=None)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, OverflowError, OSError):
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _positive_int(value, default: int = 1) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return default
    return number if number >= 1 else default


def _resolve(columns: list[str], role: str) -> str | None:
    lowered = {c.lower(): c for c in columns}
    return next((lowered[a] for a in COLUMN_ALIASES[role] if a in lowered), None)


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]


def _routing_fields(raw) -> tuple[str | None, str | None]:
    """domain / subdomain d'un routage stocké en JSON texte (ou déjà dict)."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None, None
    if isinstance(raw, dict):
        raw = raw.get("routing_plan", raw)
        domain, sub = raw.get("domain"), raw.get("subdomain")
        return (domain if isinstance(domain, str) and domain else None,
                sub if isinstance(sub, str) and sub else None)
    return None, None


def read_audit_db(path: str | Path, since: datetime | None = None) -> AuditData:
    """Lit la table gaps (et, si elle existe, audit_log) d'un audit.db, en lecture seule."""
    path = Path(path)
    if not path.is_file():
        raise SourceError(f"audit.db introuvable : {path}")
    try:
        conn = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise SourceError(f"audit.db illisible : {exc}") from exc
    conn.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if GAPS_TABLE not in tables:
            raise SourceError(f"table '{GAPS_TABLE}' absente de {path.name} (tables : {sorted(tables) or 'aucune'})")
        cols = _columns(conn, GAPS_TABLE)
        c = {role: _resolve(cols, role) for role in COLUMN_ALIASES}
        if c["topic"] is None:
            raise SourceError(f"table '{GAPS_TABLE}' sans colonne de sujet (colonnes : {cols}). "
                              f"Ajustez COLUMN_ALIASES dans gaps/readers.py.")
        data = AuditData()
        n_rows = n_skipped_old = n_empty = 0
        for row in conn.execute(f'SELECT * FROM "{GAPS_TABLE}"'):
            n_rows += 1
            topic = clean_text(row[c["topic"]] or "", MAX_TOPIC_CHARS)
            if not topic:
                n_empty += 1
                continue
            when = parse_timestamp(row[c["timestamp"]]) if c["timestamp"] else None
            if since is not None and when is not None and when < since:
                n_skipped_old += 1
                continue
            data.observations.append(Observation(
                topic=topic, origin="audit",
                weight=_positive_int(row[c["count"]]) if c["count"] else 1,
                reason=(str(row[c["reason"]]).strip() or None) if c["reason"] and row[c["reason"]] is not None else None,
                request_id=(str(row[c["request_id"]]).strip() or None) if c["request_id"] and row[c["request_id"]] is not None else None,
                timestamp=when,
                domain=(str(row[c["domain"]]).strip() or None) if c["domain"] and row[c["domain"]] else None,
                subdomain=(str(row[c["subdomain"]]).strip() or None) if c["subdomain"] and row[c["subdomain"]] else None,
            ))
        if LOG_TABLE in tables:
            data.contexts = _read_contexts(conn)
        data.info = {"kind": "audit_db", "path": str(path), "rows": n_rows, "observations": len(data.observations),
                     "skipped_before_since": n_skipped_old, "skipped_empty_topic": n_empty,
                     "audit_log_requests": len(data.contexts)}
        return data
    except sqlite3.Error as exc:
        raise SourceError(f"lecture de {path.name} impossible : {exc}") from exc
    finally:
        conn.close()


def _read_contexts(conn: sqlite3.Connection) -> dict[str, AuditContext]:
    cols = _columns(conn, LOG_TABLE)
    c = {role: _resolve(cols, role) for role in COLUMN_ALIASES}
    if c["request_id"] is None:
        return {}
    contexts = {}
    for row in conn.execute(f'SELECT * FROM "{LOG_TABLE}"'):
        request_id = row[c["request_id"]]
        if request_id is None:
            continue
        domain = sub = None
        if c["routing"] and row[c["routing"]] is not None:
            domain, sub = _routing_fields(row[c["routing"]])
        if c["domain"] and row[c["domain"]]:
            domain = str(row[c["domain"]])
        if c["subdomain"] and row[c["subdomain"]]:
            sub = str(row[c["subdomain"]])
        question = row[c["question"]] if c["question"] else None
        contexts[str(request_id)] = AuditContext(
            question=clean_text(question, MAX_QUESTION_CHARS) if question else None, domain=domain, subdomain=sub)
    return contexts


def read_gaps_api(base_url: str, since: datetime | None = None, timeout: float = 10.0) -> AuditData:
    """Lit GET {base_url}/gaps (lacunes déjà regroupées par sujet, avec un compteur si l'API en fournit un)."""
    import httpx

    url = base_url.rstrip("/") + "/gaps"
    try:
        response = httpx.get(url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise SourceError(f"GET {url} impossible : {type(exc).__name__} {exc}") from exc
    except ValueError as exc:
        raise SourceError(f"GET {url} : réponse JSON invalide") from exc
    return parse_gaps_payload(payload, source=url)


def parse_gaps_payload(payload, source: str = "api") -> AuditData:
    items = payload
    if isinstance(payload, dict):
        items = next((payload[k] for k in API_LIST_KEYS if isinstance(payload.get(k), list)), None)
    if not isinstance(items, list):
        raise SourceError(f"{source} : liste de lacunes introuvable (attendu : liste ou objet avec une des clés {API_LIST_KEYS})")
    data = AuditData()
    for item in items:
        if isinstance(item, str):
            item = {"topic": item}
        if not isinstance(item, dict):
            continue
        low = {str(k).lower(): v for k, v in item.items()}
        topic_key = next((a for a in COLUMN_ALIASES["topic"] if a in low), None)
        topic = clean_text(low.get(topic_key) or "", MAX_TOPIC_CHARS) if topic_key else ""
        if not topic:
            continue
        count_key = next((a for a in COLUMN_ALIASES["count"] if a in low), None)
        reason_key = next((a for a in COLUMN_ALIASES["reason"] if a in low), None)
        data.observations.append(Observation(
            topic=topic, origin="audit",
            weight=_positive_int(low[count_key]) if count_key else 1,
            reason=str(low[reason_key]) if reason_key and low[reason_key] else None,
            domain=low.get("domain") or None, subdomain=low.get("subdomain") or None,
            timestamp=parse_timestamp(next((low[a] for a in COLUMN_ALIASES["timestamp"] if a in low), None)),
        ))
    data.info = {"kind": "api", "url": source, "observations": len(data.observations)}
    return data


def read_eval_report(path: str | Path) -> EvalData:
    """Lit eval_report.json (contrat T1) : on n'utilise que run_id et failures."""
    path = Path(path)
    if not path.is_file():
        raise SourceError(f"eval_report.json introuvable : {path}")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SourceError(f"eval_report.json illisible : {exc}") from exc
    if not isinstance(report, dict):
        raise SourceError("eval_report.json : un objet JSON est attendu")
    failures = report.get("failures", [])
    if not isinstance(failures, list):
        raise SourceError("eval_report.json : 'failures' doit être une liste")
    valid = [f for f in failures if isinstance(f, dict) and f.get("question_id")]
    return EvalData(run_id=report.get("run_id"), failures=valid,
                    info={"path": str(path), "run_id": report.get("run_id"), "n_failures": len(valid),
                          "n_malformed_failures": len(failures) - len(valid)})


def read_questions(path: str | Path | None) -> dict[str, str]:
    """data/eval/questions.json -> {question_id: texte}. Absent ou illisible -> {} (source facultative)."""
    if path is None or not Path(path).is_file():
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if isinstance(payload, dict):
        payload = next((payload[k] for k in ("questions", "items", "data") if isinstance(payload.get(k), list)), [])
    result = {}
    for item in payload if isinstance(payload, list) else []:
        if not isinstance(item, dict):
            continue
        qid = item.get("question_id") or item.get("id")
        text = item.get("question") or item.get("text") or item.get("query")
        if qid and isinstance(text, str) and text.strip():
            result[str(qid)] = clean_text(text, MAX_QUESTION_CHARS)
    return result

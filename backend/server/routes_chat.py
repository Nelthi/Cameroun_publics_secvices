"""Routes de l'interface UTILISATEUR : discussions et questions sur les procédures."""
from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from . import db

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _user(x_user_id: Optional[str]) -> str:
    return (x_user_id or "demo").strip()[:64] or "demo"


class NewConversation(BaseModel):
    title: Optional[str] = None


class NewMessage(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


def _own(conn, conversation_id: str, user: str):
    row = conn.execute("SELECT * FROM conversations WHERE id=? AND user_id=?", (conversation_id, user)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Discussion introuvable.")
    return row


def _message(row) -> dict:
    return {"id": row["id"], "role": row["role"], "content": row["content"], "status": row["status"],
            "sources": json.loads(row["sources_json"] or "[]"), "request_id": row["request_id"],
            "created_at": row["created_at"]}


@router.get("/conversations")
def list_conversations(x_user_id: Optional[str] = Header(default=None)):
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM conversations WHERE user_id=? ORDER BY updated_at DESC",
                            (_user(x_user_id),)).fetchall()
    return [{"id": r["id"], "title": r["title"], "created_at": r["created_at"], "updated_at": r["updated_at"]} for r in rows]


@router.post("/conversations", status_code=201)
def create_conversation(body: NewConversation, x_user_id: Optional[str] = Header(default=None)):
    cid, stamp = uuid.uuid4().hex[:12], db.now()
    with db.connect() as conn:
        conn.execute("INSERT INTO conversations (id, user_id, title, created_at, updated_at) VALUES (?,?,?,?,?)",
                     (cid, _user(x_user_id), (body.title or "Nouvelle discussion")[:80], stamp, stamp))
    return {"id": cid, "title": body.title or "Nouvelle discussion", "created_at": stamp, "updated_at": stamp}


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, x_user_id: Optional[str] = Header(default=None)):
    with db.connect() as conn:
        conv = _own(conn, conversation_id, _user(x_user_id))
        msgs = conn.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY id", (conversation_id,)).fetchall()
    return {"id": conv["id"], "title": conv["title"], "messages": [_message(m) for m in msgs]}


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, x_user_id: Optional[str] = Header(default=None)):
    with db.connect() as conn:
        _own(conn, conversation_id, _user(x_user_id))
        conn.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))
        conn.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))


@router.post("/conversations/{conversation_id}/messages")
def send_message(conversation_id: str, body: NewMessage, x_user_id: Optional[str] = Header(default=None)):
    """Enregistre la question, la fait traiter par la chaîne T1 -> T2 -> T3 (via T4) et renvoie la réponse."""
    user, text = _user(x_user_id), body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="La question ne peut pas être vide.")
    with db.connect() as conn:
        conv = _own(conn, conversation_id, user)
        first = conn.execute("SELECT COUNT(*) c FROM messages WHERE conversation_id=?", (conversation_id,)).fetchone()["c"] == 0
        conn.execute("INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?,?,?,?)",
                     (conversation_id, "user", text, db.now()))
        if first and conv["title"] == "Nouvelle discussion":
            conn.execute("UPDATE conversations SET title=? WHERE id=?", (text[:60], conversation_id))

    from app import pipeline  # T4 : appelle T1, T2, T3 et écrit l'audit

    result = pipeline.run(text)
    from . import services

    titles = {r["document_id"]: r.get("title") for r in services.registry()}
    sources = [{**s, "title": titles.get(s["document_id"]) or s["document_id"]} for s in (result.get("sources") or [])]
    with db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO messages (conversation_id, role, content, status, sources_json, request_id, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (conversation_id, "assistant", result.get("answer", ""), result.get("status"),
             json.dumps(sources, ensure_ascii=False), result.get("request_id"), db.now()))
        conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (db.now(), conversation_id))
        row = conn.execute("SELECT * FROM messages WHERE id=?", (cur.lastrowid,)).fetchone()
    return _message(row)

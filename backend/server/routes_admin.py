"""Routes de l'interface ADMINISTRATEUR : envoi de documents, données enregistrées, lancement des phases."""
from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel

from backend.ai import metadata as ai_metadata
from backend.knowledge_base.collectors import DocumentMetadata
from backend.knowledge_base.collectors.exceptions import CollectorError

from . import jobs, services
from .settings import admin_token


def require_admin(x_admin_token: Optional[str] = Header(default=None)):
    expected = admin_token()
    if expected and x_admin_token != expected:
        raise HTTPException(status_code=401, detail="Jeton administrateur invalide.")


router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)], tags=["admin"])


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w.\- ]", "_", Path(name or "document").name) or "document"


async def _save_temp(upload: UploadFile, folder: Path) -> Path:
    target = folder / _safe_name(upload.filename)
    with target.open("wb") as out:
        shutil.copyfileobj(upload.file, out)
    return target


@router.get("/overview")
def overview():
    return services.overview()


@router.post("/suggest-metadata")
async def suggest(file: UploadFile = File(...)):
    """Groq propose titre, institution, date, domaine et sous-domaine à partir du début du fichier."""
    with tempfile.TemporaryDirectory() as tmp:
        path = await _save_temp(file, Path(tmp))
        excerpt = ai_metadata.extract_excerpt(path)
    known = {d["subdomain"] for d in services.list_documents() if d.get("subdomain")}
    return ai_metadata.suggest_metadata(file.filename or "document", excerpt, known)


@router.post("/documents")
async def upload_documents(files: List[UploadFile] = File(...), metadata: str = Form("[]"),
                           auto_metadata: bool = Form(True)):
    """Envoi de plusieurs documents. `metadata` : liste JSON alignée sur `files`
    ({title, institution, date, domain, subdomain}). Champs manquants : proposés par Groq si
    `auto_metadata` est vrai."""
    try:
        provided = json.loads(metadata or "[]")
        assert isinstance(provided, list)
    except (ValueError, AssertionError):
        raise HTTPException(status_code=400, detail="metadata doit être une liste JSON.")
    col = services.collector()
    known = {d["subdomain"] for d in services.list_documents() if d.get("subdomain")}
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, upload in enumerate(files):
            entry = {"filename": upload.filename, "ok": False}
            try:
                path = await _save_temp(upload, Path(tmp))
                meta = dict(provided[i]) if i < len(provided) and isinstance(provided[i], dict) else {}
                required = ("title", "institution", "date", "domain", "subdomain")
                if auto_metadata and any(not str(meta.get(k, "")).strip() for k in required):
                    guess = ai_metadata.suggest_metadata(upload.filename or "", ai_metadata.extract_excerpt(path), known)
                    for k in required:
                        if not str(meta.get(k, "")).strip():
                            meta[k] = guess.get(k, "")
                    entry["metadata_source"] = "groq" if guess.get("ai") else "heuristique"
                imported = col.import_document(path, DocumentMetadata(**{k: str(meta.get(k, "")) for k in required}),
                                                original_filename=upload.filename)
                entry.update(ok=True, document_id=imported.document_id, duplicate=imported.is_duplicate,
                             title=meta.get("title"), subdomain=meta.get("subdomain"))
            except CollectorError as exc:
                entry["error"] = str(exc)
            except Exception as exc:  # noqa: BLE001
                entry["error"] = f"{type(exc).__name__}: {exc}"
            results.append(entry)
    return {"results": results, "stored": sum(1 for r in results if r["ok"] and not r.get("duplicate"))}


@router.get("/documents")
def documents():
    return services.list_documents()


@router.get("/documents/{document_id}/text")
def document_text(document_id: str, limit: int = 20000):
    try:
        return services.processed_text(document_id, limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/chunks")
def chunks(document_id: Optional[str] = None, limit: int = 50, offset: int = 0):
    return services.list_chunks(document_id, min(limit, 200), offset)


@router.get("/vectors")
def vectors(limit: int = 20, offset: int = 0):
    return services.vectors_info(min(limit, 100), offset)


@router.get("/audit")
def audit(limit: int = 30):
    return {"requests": services.audit_rows(min(limit, 200)), "gaps": _gaps()}


def _gaps():
    from app import audit as t4_audit

    return t4_audit.list_gaps()


class RunBody(BaseModel):
    document_ids: Optional[List[str]] = None
    mode: str = "native"  # "native" = code d'Alex, "ai" = agent IA (Groq)


@router.post("/run/{phase}")
def run(phase: str, body: RunBody):
    if phase not in {"extract", "chunk", "index", "all"}:
        raise HTTPException(status_code=404, detail="phase inconnue (extract, chunk, index, all)")
    if body.mode not in {"native", "ai"}:
        raise HTTPException(status_code=422, detail="mode doit valoir 'native' ou 'ai'")
    params = {"phase": phase, "mode": body.mode, "document_ids": body.document_ids}
    return jobs.start(phase, params, lambda job: services.run_phase(job, phase, body.document_ids, body.mode))


@router.get("/jobs")
def list_jobs(limit: int = 15):
    return jobs.recent(limit)


@router.get("/jobs/{job_id}")
def job(job_id: str):
    data = jobs.get(job_id)
    if data is None:
        raise HTTPException(status_code=404, detail="tâche inconnue")
    return data.data

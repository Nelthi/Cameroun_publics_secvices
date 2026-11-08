"""Branchements de DÉMONSTRATION (sans le vrai code de la Phase 2) : permettent de tester T3 seul.

Le « index » est simplement le décompte des fragments déjà écrits dans demo_store/chunks :
aucun vecteur n'est calculé et `dim` vaut null. Pour la vraie base, écrire phase2_hooks.py (voir README).
"""
import hashlib
import json
import shutil
from pathlib import Path

from .ocr import extract_document
from .pipeline import Hooks

STORE = Path("demo_store")


def _ingest(chemin, meta):
    sha = hashlib.sha256(Path(chemin).read_bytes()).hexdigest()
    doc_id = "DOC-" + sha[:8].upper()
    dest = STORE / "raw" / (meta["domain"] or "autre") / (meta["subdomain"] or "autre") / f"{doc_id}{Path(chemin).suffix.lower()}"
    if dest.exists():
        return {"document_id": doc_id, "stored_path": str(dest), "status": "duplicate"}
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(chemin, dest)
    return {"document_id": doc_id, "stored_path": str(dest), "status": "stored"}


def _stats():
    n = sum(len(json.loads(f.read_text(encoding="utf-8"))["chunks"]) for f in (STORE / "chunks").glob("*.json")) \
        if (STORE / "chunks").exists() else 0
    return {"n_chunks": n, "dim": None}


def get_hooks():
    from chunking import chunk_document  # module de la Phase 2 (t3_chunking), à mettre sur PYTHONPATH
    return Hooks(ingest=_ingest, extract=extract_document, chunk=chunk_document,
                 index_stats=_stats, build_index=_stats, data_dir=str(STORE))

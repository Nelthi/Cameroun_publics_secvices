"""Opérations métier de l'API : une fonction par phase, branchées sur le code des quatre membres.

Phase 2 : T1 (stockage) -> T2 (extraction) -> T3 (découpage : natif d'Alex OU IA) -> T4 (vecteurs FAISS).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from backend.knowledge_base.collectors import DocumentCollector
from backend.knowledge_base.processors.processor import DocumentProcessor

from . import db
from .settings import data_root

_EMBEDDER = None


def get_embedder():
    """Modèle d'embedding de T4 (BAAI/bge-m3), chargé une seule fois."""
    global _EMBEDDER
    if _EMBEDDER is None:
        from backend.rag.embedder import Embedder

        _EMBEDDER = Embedder()
    return _EMBEDDER


# ------------------------------------------------------------------ chemins et registre
def collector() -> DocumentCollector:
    return DocumentCollector(data_root=data_root())


def registry() -> list:
    return collector().repository.list_documents()


def registry_ids() -> set:
    return {r["document_id"] for r in registry()}


def processed_file(document_id: str) -> Optional[Path]:
    found = list((data_root() / "processed").rglob(f"{document_id}.json"))
    return found[0] if found else None


def chunks_file(document_id: str) -> Path:
    return data_root() / "chunks" / f"{document_id}.json"


def index_paths():
    root = data_root() / "indexes"
    return root / "faiss.index", root / "chunk_mapping.json"


def _mapping() -> dict:
    _, mapping_path = index_paths()
    if not mapping_path.exists():
        return {}
    return json.loads(mapping_path.read_text(encoding="utf-8"))


def _last_modes() -> dict:
    with db.connect() as conn:
        rows = conn.execute("SELECT document_id, mode FROM phase_log WHERE phase='chunk' ORDER BY id").fetchall()
    return {r["document_id"]: r["mode"] for r in rows}


def log_phase(document_id: str, phase: str, mode: Optional[str] = None, detail: str = ""):
    with db.connect() as conn:
        conn.execute("INSERT INTO phase_log (document_id, phase, mode, detail, created_at) VALUES (?,?,?,?,?)",
                     (document_id, phase, mode, detail, db.now()))


# ------------------------------------------------------------------ lecture des données
def list_documents() -> list:
    indexed = {c["document_id"] for c in _mapping().values()}
    modes = _last_modes()
    result = []
    for r in registry():
        did = r["document_id"]
        cf = chunks_file(did)
        n_chunks = len(json.loads(cf.read_text(encoding="utf-8"))["chunks"]) if cf.exists() else 0
        result.append({
            "document_id": did, "title": r.get("title"), "institution": r.get("institution"),
            "domain": r.get("domain"), "subdomain": r.get("subdomain"), "date": r.get("document_date"),
            "original_filename": r.get("original_filename"), "file_format": r.get("file_format"),
            "file_size": r.get("file_size"), "upload_date": r.get("upload_date"),
            "extracted": processed_file(did) is not None, "chunked": cf.exists(),
            "indexed": did in indexed, "chunk_count": n_chunks, "chunk_mode": modes.get(did),
        })
    return result


def overview() -> dict:
    docs = list_documents()
    index_path, _ = index_paths()
    vectors, dim = 0, None
    if index_path.exists():
        try:
            import faiss

            idx = faiss.read_index(str(index_path))
            vectors, dim = idx.ntotal, idx.d
        except Exception:  # noqa: BLE001
            pass
    from backend.ai import groq
    from backend.rag.config import MODEL_NAME

    return {
        "documents": len(docs), "extracted": sum(d["extracted"] for d in docs),
        "chunked": sum(d["chunked"] for d in docs), "indexed": sum(d["indexed"] for d in docs),
        "chunks": sum(d["chunk_count"] for d in docs), "vectors": vectors, "vector_dim": dim,
        "embedding_model": MODEL_NAME, "groq_configured": groq.is_configured(),
        "groq_model": groq.quality_model(), "groq_fast_model": groq.fast_model(),
    }


def processed_text(document_id: str, limit: int = 20000) -> dict:
    path = processed_file(document_id)
    if path is None:
        raise FileNotFoundError("Texte non extrait : lancez d'abord l'extraction (T2).")
    data = json.loads(path.read_text(encoding="utf-8"))
    segments = data["content"]["segments"]
    text, used = "", []
    for seg in segments:
        if len(text) >= limit:
            break
        used.append({"page_number": seg.get("page_number"), "text": seg["text"][: limit - len(text)]})
        text += seg["text"]
    return {"document_id": document_id, "status": data.get("processing", {}).get("status"),
            "warnings": data.get("processing", {}).get("warnings", []),
            "character_count": data.get("processing", {}).get("character_count"),
            "segments": used, "truncated": len(text) >= limit}


def list_chunks(document_id: Optional[str] = None, limit: int = 50, offset: int = 0) -> dict:
    ids = [document_id] if document_id else sorted(registry_ids())
    rows = []
    for did in ids:
        cf = chunks_file(did)
        if cf.exists():
            data = json.loads(cf.read_text(encoding="utf-8"))
            rows += [{**c, "document_id": did} for c in data["chunks"]]
    return {"total": len(rows), "items": rows[offset: offset + limit]}


def vectors_info(limit: int = 20, offset: int = 0) -> dict:
    index_path, _ = index_paths()
    mapping = _mapping()
    if not index_path.exists() or not mapping:
        return {"built": False, "total": 0, "dim": None, "items": []}
    import faiss
    import numpy as np

    index = faiss.read_index(str(index_path))
    from backend.rag.config import MODEL_NAME

    items = []
    for i in range(offset, min(offset + limit, index.ntotal)):
        vec = np.asarray(index.reconstruct(i), dtype="float32")
        item = mapping.get(str(i), {})
        items.append({"vector_id": i, "chunk_id": item.get("chunk_id"), "document_id": item.get("document_id"),
                      "source_page": item.get("source_page"), "norm": round(float(np.linalg.norm(vec)), 4),
                      "first_values": [round(float(x), 4) for x in vec[:8]],
                      "text_preview": (item.get("text") or "")[:120]})
    return {"built": True, "total": index.ntotal, "dim": index.d, "model": MODEL_NAME,
            "index_type": type(index).__name__, "items": items}


def audit_rows(limit: int = 30) -> list:
    from app import audit

    with audit._connect() as conn:
        rows = conn.execute("SELECT request_id, timestamp, question, status, duration_ms, error "
                            "FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------------------ phases
def phase_extract(document_id: str) -> dict:
    col = collector()
    processor = DocumentProcessor(data_root=data_root(), database_path=col.database_path)
    result = processor.process_document(document_id).to_dict()
    log_phase(document_id, "extract", detail=result["status"])
    return result


def phase_chunk(document_id: str, mode: str = "native", report: Optional[dict] = None) -> dict:
    from backend.pipeline.adapters import t2_output_to_t3_input
    from backend.pipeline.t2_to_t3 import chunk_from_t2

    path = processed_file(document_id)
    if path is None:
        raise FileNotFoundError("Texte non extrait : lancez d'abord l'extraction (T2).")
    chunks_dir = data_root() / "chunks"
    if mode == "native":  # code d'Alex
        out, count = chunk_from_t2(path, chunks_dir)
    elif mode == "ai":  # découpage sémantique par agent IA (Groq)
        from chunking import validate_output
        from chunking.ai_chunker import chunk_document_ai

        processed = json.loads(path.read_text(encoding="utf-8"))
        result = chunk_document_ai(t2_output_to_t3_input(processed), report=report)
        assert not validate_output(result)
        out = chunks_dir / f"{document_id}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        count = len(result["chunks"])
    else:
        raise ValueError("mode doit valoir 'native' ou 'ai'")
    log_phase(document_id, "chunk", mode=mode, detail=f"{count} fragments")
    return {"document_id": document_id, "mode": mode, "chunks": count, "path": str(out)}


def phase_index() -> dict:
    """Vectorise tous les fragments des documents enregistrés (T4) et recharge la recherche."""
    from backend.rag.chunk_loader import _parse_document
    from backend.rag.vector_store import build_index, save_index

    ids = registry_ids()
    chunks, seen = [], set()
    for file in sorted((data_root() / "chunks").glob("*.json")):
        data = json.loads(file.read_text(encoding="utf-8"))
        if data.get("document_id") in ids:  # ignore les fichiers d'exemple non enregistrés
            chunks.extend(_parse_document(data, file.name, seen))
    if not chunks:
        raise ValueError("Aucun fragment à vectoriser : lancez d'abord le découpage.")
    index, mapping = build_index(chunks, get_embedder())
    index_path, mapping_path = index_paths()
    save_index(index, mapping, index_path, mapping_path)
    import backend.rag as rag

    rag.reset_store()
    for did in {c["document_id"] for c in chunks}:
        log_phase(did, "index", detail=f"dim {index.d}")
    return {"vectors": int(index.ntotal), "dim": int(index.d), "documents": len({c['document_id'] for c in chunks})}


def run_phase(job, phase: str, document_ids: Optional[list], mode: str = "native") -> dict:
    """Exécute une phase (ou `all`) pour des documents ; journalise dans le job."""
    from chunking.ai_chunker import AIChunkingError

    ids = document_ids or [r["document_id"] for r in registry()]
    errors, outcome = [], {"extract": [], "chunk": [], "index": None}
    steps = [phase] if phase != "all" else ["extract", "chunk", "index"]
    total = sum(len(ids) if s != "index" else 1 for s in steps)
    done = 0
    for step in steps:
        if step == "index":
            job.log("Vectorisation (bge-m3) et construction de l'index FAISS...")
            try:
                outcome["index"] = phase_index()
                job.log(f"Index prêt : {outcome['index']['vectors']} vecteurs, dimension {outcome['index']['dim']}.")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"index : {exc}")
                job.log(f"ERREUR index : {exc}")
            done += 1
            job.progress(done / total)
            continue
        for did in ids:
            try:
                if step == "extract":
                    res = phase_extract(did)
                    outcome["extract"].append(res)
                    job.log(f"[T2 extraction] {did} : {res['status']}, {res['character_count']} caractères.")
                else:
                    report: dict = {}
                    res = phase_chunk(did, mode, report)
                    res["report"] = report
                    outcome["chunk"].append(res)
                    label = "IA Groq" if mode == "ai" else "code d'Alex"
                    job.log(f"[T3 découpage – {label}] {did} : {res['chunks']} fragments.")
            except AIChunkingError as exc:  # inutile de continuer : même cause pour tous les documents
                errors.append(f"{did} : {exc}")
                job.log(f"ERREUR découpage IA : {exc}")
                job.progress(1.0)
                return {**outcome, "errors": errors}
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{did} : {exc}")
                job.log(f"ERREUR {step} {did} : {exc}")
            done += 1
            job.progress(done / total)
    return {**outcome, "errors": errors}

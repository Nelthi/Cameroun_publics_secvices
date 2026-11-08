"""Orchestration de la mise à jour de la base : nouveaux documents -> chaîne Phase 2 -> index -> kb_update.json."""
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable


@dataclass
class Hooks:
    """Points de branchement sur le code de la Phase 2 (on l'appelle, on ne le modifie pas).

    ingest(chemin, meta)      -> {"document_id", "stored_path", "status"}   ("stored" ou "duplicate")
    extract(document_id, chemin_stocké) -> (dict_t2, ocr_utilisé)
    chunk(dict_t2)            -> dict T3 (document_id, chunks[])           (module `chunking`)
    index_stats()             -> {"n_chunks": int, "dim": int | None}      (état actuel de l'index)
    build_index()             -> {"n_chunks": int, "dim": int | None}      (reconstruit puis renvoie l'état)
    """
    ingest: Callable
    extract: Callable
    chunk: Callable
    index_stats: Callable
    build_index: Callable
    data_dir: str = "data"   # où écrire data/processed et data/chunks


def _ecrire(chemin, data):
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run(documents, hooks, gap_ids_connus=None, out="data/reports/kb_update.json"):
    """Traite la liste de documents (manifeste) et écrit kb_update.json + kb_update_details.json."""
    avant = hooks.index_stats()
    ajoutes, details, ignores = [], [], []
    for doc in documents:
        meta = {k: doc.get(k) for k in ("title", "institution", "domain", "subdomain", "date", "source_url")}
        try:
            ing = hooks.ingest(doc["path"], meta)
            if ing["status"] == "duplicate":
                ignores.append({"path": doc["path"], "reason": "doublon", "document_id": ing["document_id"]})
                continue
            t2, ocr_used = hooks.extract(ing["document_id"], ing["stored_path"])
            sortie = hooks.chunk(t2)
            _ecrire(Path(hooks.data_dir) / "processed" / (meta["domain"] or "autre") / (meta["subdomain"] or "autre")
                    / f"{ing['document_id']}.json", t2)
            _ecrire(Path(hooks.data_dir) / "chunks" / f"{ing['document_id']}.json", sortie)
        except Exception as e:  # un document en échec ne bloque pas les autres
            ignores.append({"path": doc["path"], "reason": f"{type(e).__name__}: {e}"})
            continue
        ajoutes.append({"document_id": ing["document_id"], "institution": doc.get("institution") or "à confirmer",
                        "ocr_used": ocr_used})
        details.append({"document_id": ing["document_id"], "title": doc.get("title"), "source_url": doc.get("source_url"),
                        "gap_ids": doc.get("gap_ids", []), "n_pages": len(t2["pages"]),
                        "n_chunks": len(sortie["chunks"]), "warnings": t2["warnings"]})

    apres = hooks.build_index() if ajoutes else avant
    visees = sorted({g for d in details for g in d["gap_ids"] if gap_ids_connus is None or g in gap_ids_connus})
    rapport = {
        "update_date": datetime.now().replace(microsecond=0).isoformat(),
        "gaps_addressed": visees,
        "documents_added": ajoutes,
        "index": {"n_chunks_before": avant["n_chunks"], "n_chunks_after": apres["n_chunks"], "dim": apres["dim"]},
        "status": "indexed" if ajoutes else "no_change",
    }
    _ecrire(out, rapport)
    _ecrire(Path(out).with_name("kb_update_details.json"), {"documents": details, "skipped": ignores})
    return rapport

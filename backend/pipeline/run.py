"""Exécute la chaîne complète : ingestion -> extraction -> découpage -> index.

Depuis la racine du projet :
    python -m backend.pipeline.run fichier.pdf --title "..." --institution DGSN \
        --date 2026-11-04 --domain public_services --subdomain national_identity_card
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.knowledge_base.collectors import DocumentCollector, DocumentMetadata
from backend.knowledge_base.processors.processor import DocumentProcessor

from .t2_to_t3 import chunk_from_t2


def run_pipeline(source, metadata: DocumentMetadata, data_root="data", embedder=None,
                 build_faiss=True):
    """Retourne un dict avec document_id et les chemins produits à chaque étape."""
    data_root = Path(data_root)

    # T1 — ingestion et stockage
    collector = DocumentCollector(data_root=data_root)
    imported = collector.import_document(source, metadata)
    document_id = imported.document_id
    out = {"document_id": document_id, "duplicate": imported.is_duplicate}

    # T2 — extraction et nettoyage (lit directement le registre de T1)
    processor = DocumentProcessor(data_root=data_root,
                                  database_path=collector.database_path)
    processed = processor.process_document(document_id)
    processed_path = data_root / processed.output_path
    out["processed"] = str(processed_path)
    out["warnings"] = processed.warnings

    # T3 — découpage (liaison T2 -> T3 puis code d'Alex)
    chunks_path, chunk_count = chunk_from_t2(processed_path, data_root / "chunks")
    out["chunks"] = str(chunks_path)
    out["chunk_count"] = chunk_count

    # T4 — vectorisation et index FAISS
    if build_faiss and out["chunk_count"]:
        from backend.rag.chunk_loader import load_chunks
        from backend.rag.embedder import Embedder
        from backend.rag.vector_store import build_index, save_index
        index, mapping = build_index(load_chunks(data_root / "chunks"),
                                     embedder or Embedder())
        index_dir = data_root / "indexes"
        save_index(index, mapping, index_dir / "faiss.index",
                   index_dir / "chunk_mapping.json")
        out["index"] = str(index_dir / "faiss.index")
        out["vectors"] = int(index.ntotal)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Chaîne complète T1 -> T4")
    ap.add_argument("source")
    ap.add_argument("--title", required=True)
    ap.add_argument("--institution", required=True)
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--domain", required=True)
    ap.add_argument("--subdomain", required=True)
    ap.add_argument("--data-root", default="data")
    args = ap.parse_args(argv)
    meta = DocumentMetadata(title=args.title, institution=args.institution,
                            date=args.date, domain=args.domain, subdomain=args.subdomain)
    print(json.dumps(run_pipeline(args.source, meta, args.data_root),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

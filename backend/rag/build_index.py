"""Construit l'index FAISS à partir des fragments de T3.

Usage (depuis la racine du projet) :
    python -m backend.rag.build_index
    python -m backend.rag.build_index --chunks-dir autre/dossier
"""
import argparse

from .chunk_loader import load_chunks
from .config import CHUNKS_DIR, INDEX_PATH, MAPPING_PATH
from .embedder import Embedder
from .vector_store import build_index, save_index


def main(argv=None):
    parser = argparse.ArgumentParser(description="Construction de l'index FAISS (T4)")
    parser.add_argument("--chunks-dir", default=CHUNKS_DIR)
    parser.add_argument("--index-path", default=INDEX_PATH)
    parser.add_argument("--mapping-path", default=MAPPING_PATH)
    args = parser.parse_args(argv)

    chunks = load_chunks(args.chunks_dir)
    docs = {c["document_id"] for c in chunks}
    print(f"{len(chunks)} fragments lus, {len(docs)} document(s). Vectorisation...")

    index, mapping = build_index(chunks, Embedder())
    save_index(index, mapping, args.index_path, args.mapping_path)
    print(f"Index : {args.index_path} ({index.ntotal} vecteurs, dim {index.d})")
    print(f"Mapping : {args.mapping_path}")


if __name__ == "__main__":
    main()

"""Liaison T2 -> T3 : prend le document extrait par T2 et lance le découpage d'Alex.

    python -m backend.pipeline.t2_to_t3 DOC-XXXXXXXX
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from chunking import chunk_document, validate_output

from .adapters import t2_output_to_t3_input


def chunk_from_t2(processed_path, chunks_dir):
    """Lit la sortie de T2, applique T3, vérifie le contrat, écrit data/chunks/{id}.json."""
    processed = json.loads(Path(processed_path).read_text(encoding="utf-8"))
    result = chunk_document(t2_output_to_t3_input(processed))
    errors = validate_output(result)
    if errors:
        raise ValueError("Sortie T3 hors contrat : " + " ; ".join(errors))
    out = Path(chunks_dir) / f"{result['document_id']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return out, len(result["chunks"])


def main(argv=None):
    ap = argparse.ArgumentParser(description="T2 -> T3 : découpe un document déjà extrait")
    ap.add_argument("document_id")
    ap.add_argument("--data-root", default="data")
    args = ap.parse_args(argv)
    root = Path(args.data_root)
    found = list((root / "processed").rglob(f"{args.document_id}.json"))
    if not found:
        raise SystemExit(f"Aucun fichier T2 pour {args.document_id} dans {root}/processed "
                         "(T2 n'a pas encore traité ce document).")
    out, n = chunk_from_t2(found[0], root / "chunks")
    print(f"{n} fragments -> {out}")
    if n == 0:
        print("attention : 0 fragment (PDF scanné ? voir les warnings de T2)")


if __name__ == "__main__":
    main()

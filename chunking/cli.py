"""Ligne de commande : python -m chunking <sortie_t2.json> [--out-dir DOSSIER]"""
import argparse
import json
from pathlib import Path

from .contract import validate_output
from .core import chunk_document


def run(input_path, out_dir="data/chunks"):
    """Lit un JSON de T2 et écrit data/chunks/{document_id}.json. Retourne (chemin, nb_fragments)."""
    doc = json.loads(Path(input_path).read_text(encoding="utf-8"))
    result = chunk_document(doc)
    errors = validate_output(result)
    if errors:
        raise ValueError("la sortie ne respecte pas le contrat : " + " ; ".join(errors))
    out = Path(out_dir) / f"{doc['document_id']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return out, len(result["chunks"])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="chunking", description="T3 - découpe un document T2 en fragments")
    ap.add_argument("input", help="fichier JSON produit par T2")
    ap.add_argument("--out-dir", default="data/chunks", help="dossier de sortie (défaut : data/chunks)")
    args = ap.parse_args(argv)
    path, n = run(args.input, args.out_dir)
    print(f"{n} fragments -> {path}")
    if n == 0:
        print("attention : 0 fragment (pages vides ? PDF scanné en amont ?)")


if __name__ == "__main__":
    main()

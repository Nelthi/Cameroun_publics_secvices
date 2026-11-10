"""Ligne de commande : python -m guardrails <fichier.json> [--out-dir DOSSIER] [--seuil 0.35]

Le fichier contient un objet (ou une liste d'objets) de la forme :
  {"question": "...", "draft": {<sortie de T2>}, "passages": [{"chunk_id": "...", "text": "..."}]}
"""
import argparse
import json
import sys
from pathlib import Path

from .core import SEUIL_SCORE, verifier_brouillon


def run(input_path, out_dir="data/validated", seuil=SEUIL_SCORE):
    """Traite un fichier d'entrées, écrit data/validated/{request_id}.json. Retourne la liste des sorties."""
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else [data]
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    resultats = []
    for it in items:
        if it.get("passages") is None:
            print(f"attention : pas de 'passages' pour {it['draft']['request_id']} : "
                  "citations et contenu non vérifiés contre les documents", file=sys.stderr)
        res = verifier_brouillon(it["draft"], it["question"], it.get("passages"), seuil)
        (Path(out_dir) / f"{res['request_id']}.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        resultats.append(res)
    return resultats


def main(argv=None):
    ap = argparse.ArgumentParser(prog="guardrails", description="T3 - guardrails et lacunes")
    ap.add_argument("input", help="fichier JSON (un objet ou une liste d'objets)")
    ap.add_argument("--out-dir", default="data/validated", help="dossier de sortie (défaut : data/validated)")
    ap.add_argument("--seuil", type=float, default=SEUIL_SCORE, help=f"seuil de top_score (défaut : {SEUIL_SCORE})")
    a = ap.parse_args(argv)
    for r in run(a.input, a.out_dir, a.seuil):
        ko = [k for k, v in r["checks"].items() if not v]
        print(f"{r['request_id']}  {r['status']:<8}  échecs : {', '.join(ko) or 'aucun'}  lacunes : {len(r['gaps'])}")


if __name__ == "__main__":
    main()

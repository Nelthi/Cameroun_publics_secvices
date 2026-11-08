"""Commande : python -m kb_update.run_update --documents <manifeste.json> [--gap-report ...] [--hooks MODULE]

Lancer depuis la racine du dépôt (le dossier parent de kb_update/).
"""
import argparse
import importlib
import json
import sys
from pathlib import Path

from . import priorities
from .pipeline import run


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kb_update", description="T3 Phase 4 - extension de la base et OCR")
    ap.add_argument("--documents", required=True, help="manifeste JSON des nouveaux documents")
    ap.add_argument("--gap-report", default="data/reports/gap_report.json", help="rapport de T2")
    ap.add_argument("--out", default="data/reports/kb_update.json")
    ap.add_argument("--hooks", default="kb_update.hooks_demo",
                    help="module fournissant get_hooks() (défaut : démonstration sans la vraie Phase 2)")
    ap.add_argument("--priorites", action="store_true", help="affiche seulement les lacunes à traiter en priorité")
    a = ap.parse_args(argv)

    gaps = priorities.lire_gap_report(a.gap_report)
    docs = json.loads(Path(a.documents).read_text(encoding="utf-8"))
    base = Path(a.documents).resolve().parent
    for d in docs:  # chemins relatifs : depuis le dossier du manifeste
        d["path"] = str(base / d["path"]) if not Path(d["path"]).is_absolute() else d["path"]
    if a.priorites:
        for g in priorities.prioriser(gaps):
            print(f"{g['gap_id']}  x{g['occurrences']:<3} {g['topic']}  -> {g.get('suggested_document', '?')}")
        return
    for g in priorities.non_couvertes(gaps, docs):
        print(f"attention : {g['gap_id']} ({g['topic']}, x{g['occurrences']}) n'est visée par aucun document", file=sys.stderr)
    hooks = importlib.import_module(a.hooks).get_hooks()
    r = run(docs, hooks, {g["gap_id"] for g in gaps}, out=a.out)
    i = r["index"]
    print(f"{len(r['documents_added'])} documents ajoutés, index {i['n_chunks_before']} -> {i['n_chunks_after']} fragments, "
          f"statut {r['status']} -> {a.out}")
    skipped = json.loads(Path(a.out).with_name("kb_update_details.json").read_text(encoding="utf-8"))["skipped"]
    for s in skipped:
        print(f"ignoré : {s['path']} ({s['reason']})", file=sys.stderr)


if __name__ == "__main__":
    main()

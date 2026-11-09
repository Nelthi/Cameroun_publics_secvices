"""Ligne de commande :  python -m gaps

    # Cas normal (fichiers aux emplacements par défaut)
    python -m gaps

    # Test seul avec les faux fichiers du dossier gaps/examples/
    python -m gaps --mock

    # Chemins explicites ; GET /gaps si audit.db est indisponible
    python -m gaps --audit-db data/audit.db --eval-report data/reports/eval_report.json
    python -m gaps --api-url http://127.0.0.1:8000 --source api
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from .analyzer import DEFAULT_SIMILARITY
from .errors import GapAnalysisError
from .pipeline import DEFAULT_OUT, SOURCES, run


def format_summary(report: dict, out: Path | None) -> str:
    lines = [f"Rapport des lacunes · {report['report_date']} · {report['n_gaps']} lacune(s), "
             f"{report['summary']['total_occurrences']} occurrence(s)"]
    for gap in report["gaps"][:15]:
        lines.append(f"  {gap['gap_id']}  x{gap['occurrences']:<3} {gap['subdomain']:<24} {gap['topic'][:50]:<50} "
                     f"-> {gap['suggested_document']} · {gap['suggested_institution']}")
    if report["n_gaps"] > 15:
        lines.append(f"  ... {report['n_gaps'] - 15} autre(s) dans le fichier")
    if report["ignored_failures"]:
        lines.append(f"{len(report['ignored_failures'])} échec(s) d'évaluation écarté(s) (voir 'ignored_failures')")
    lines += [f"ATTENTION : {w}" for w in report["warnings"]]
    lines.append(f"Écrit : {out}" if out else "(rapport non écrit)")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m gaps", description="T2 · Analyse des lacunes de la base de connaissances")
    ap.add_argument("--audit-db", help="chemin de audit.db (défaut : data/audit.db, data/metadata/audit.db, audit.db)")
    ap.add_argument("--api-url", help="URL de l'API de la Phase 3 (pour GET /gaps)")
    ap.add_argument("--source", choices=SOURCES, default="auto", help="origine des lacunes d'audit (défaut : auto)")
    ap.add_argument("--eval-report", help="chemin de eval_report.json (défaut : data/reports/eval_report.json)")
    ap.add_argument("--questions", help="chemin de data/eval/questions.json (texte des questions de T1)")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help=f"rapport de sortie (défaut : {DEFAULT_OUT})")
    ap.add_argument("--since", help="ne compter que les lacunes d'audit à partir de cette date ISO 8601")
    ap.add_argument("--similarity", type=float, default=DEFAULT_SIMILARITY,
                    help=f"seuil de regroupement des sujets, de 0 à 1 (défaut : {DEFAULT_SIMILARITY})")
    ap.add_argument("--count-unexpected-answers", action="store_true",
                    help="compter aussi comme lacunes les réponses données alors qu'un refus était attendu")
    ap.add_argument("--mock", action="store_true", help="utiliser les faux fichiers de gaps/examples/ (sortie hors data/)")
    ap.add_argument("--no-write", action="store_true", help="afficher le résumé sans écrire le rapport")
    args = ap.parse_args(argv)

    try:
        if args.mock:
            from .mocks import write_mock_files
            mock_dir = Path(tempfile.mkdtemp(prefix="gaps_mock_"))
            paths = write_mock_files(mock_dir)
            args.audit_db, args.eval_report, args.questions = paths["audit_db"], paths["eval_report"], paths["questions"]
            if args.out == str(DEFAULT_OUT):
                args.out = str(mock_dir / "gap_report.json")
        report, out = run(audit_db=args.audit_db, api_url=args.api_url, source=args.source,
                          eval_report=args.eval_report, questions=args.questions,
                          out=None if args.no_write else args.out, since=args.since,
                          similarity=args.similarity, count_unexpected=args.count_unexpected_answers)
    except GapAnalysisError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    print(format_summary(report, out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

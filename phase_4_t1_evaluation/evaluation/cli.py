"""CLI : python -m evaluation.cli"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .runner import run_evaluation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 4 T1 — exécuter le jeu de test et produire les rapports."
    )
    parser.add_argument(
        "--questions",
        default="data/questions.json",
        help="Chemin vers questions.json",
    )
    parser.add_argument(
        "--reports-dir",
        default="reports",
        help="Dossier de sortie des rapports",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Identifiant de run (sinon horodatage UTC)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Autorise l'écrasement explicite d'un rapport existant",
    )
    args = parser.parse_args(argv)

    report = run_evaluation(
        questions_path=Path(args.questions),
        reports_dir=Path(args.reports_dir),
        run_id=args.run_id,
        force=args.force,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

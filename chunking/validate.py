"""Contrôle autonome : python -m chunking.validate <fichier_chunks.json>"""
import json
import sys
from pathlib import Path

from .contract import validate_output


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage : python -m chunking.validate <fichier_chunks.json>")
        return 2
    errors = validate_output(json.loads(Path(argv[0]).read_text(encoding="utf-8")))
    if errors:
        print(f"INVALIDE ({len(errors)} erreur(s)) :")
        for e in errors:
            print(" -", e)
        return 1
    print("OK : le fichier respecte le contrat T3")
    return 0


if __name__ == "__main__":
    sys.exit(main())

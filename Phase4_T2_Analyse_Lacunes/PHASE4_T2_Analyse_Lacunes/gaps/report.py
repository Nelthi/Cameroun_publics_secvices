"""Contrat de gap_report.json : validation et écriture atomique."""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

from .errors import ReportError

VALID_SOURCES = {"audit", "eval", "audit+eval"}
_GAP_ID = re.compile(r"^GAP-\d{3,}$")


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate_report(report) -> list[str]:
    """Liste des erreurs de contrat (vide = rapport conforme)."""
    if not isinstance(report, dict):
        return ["le rapport n'est pas un objet JSON"]
    errors: list[str] = []
    try:
        datetime.fromisoformat(str(report.get("report_date")))
    except ValueError:
        errors.append("report_date n'est pas une date ISO 8601")
    gaps = report.get("gaps")
    if not isinstance(gaps, list):
        return errors + ["'gaps' manquant ou n'est pas une liste"]
    if report.get("n_gaps") != len(gaps):
        errors.append(f"n_gaps ({report.get('n_gaps')}) différent du nombre de lacunes ({len(gaps)})")
    seen_ids, previous = set(), None
    for i, gap in enumerate(gaps):
        where = f"gaps[{i}]"
        if not isinstance(gap, dict):
            errors.append(f"{where} n'est pas un objet")
            continue
        if not (isinstance(gap.get("gap_id"), str) and _GAP_ID.match(gap["gap_id"])):
            errors.append(f"{where}.gap_id invalide (attendu GAP-001...)")
        elif gap["gap_id"] in seen_ids:
            errors.append(f"{where}.gap_id en double : {gap['gap_id']}")
        else:
            seen_ids.add(gap["gap_id"])
        for key in ("topic", "domain", "suggested_document", "suggested_institution"):
            if not (isinstance(gap.get(key), str) and gap[key].strip()):
                errors.append(f"{where}.{key} manquant ou vide")
        if not _is_int(gap.get("occurrences")) or gap["occurrences"] < 1:
            errors.append(f"{where}.occurrences doit être un entier >= 1")
        elif previous is not None and gap["occurrences"] > previous:
            errors.append(f"{where} : lacunes non classées par occurrences décroissantes")
        if _is_int(gap.get("occurrences")):
            previous = gap["occurrences"]
        if gap.get("source") not in VALID_SOURCES:
            errors.append(f"{where}.source doit être l'un de {sorted(VALID_SOURCES)}")
    return errors


def write_report(report: dict, path: str | Path) -> Path:
    """Valide puis écrit le rapport (fichier temporaire + remplacement : jamais de rapport à moitié écrit)."""
    errors = validate_report(report)
    if errors:
        raise ReportError("rapport invalide : " + " ; ".join(errors))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return path

"""Lecture du gap_report.json de T2 et ordre de priorité des lacunes à combler."""
import json
from pathlib import Path


def lire_gap_report(chemin):
    data = json.loads(Path(chemin).read_text(encoding="utf-8"))
    return data["gaps"]


def prioriser(gaps):
    """Les lacunes les plus fréquentes d'abord (à égalité : ordre du rapport)."""
    return sorted(gaps, key=lambda g: -g["occurrences"])


def non_couvertes(gaps, documents):
    """Lacunes du rapport qu'aucun document de la liste ne vise."""
    visees = {gid for d in documents for gid in d.get("gap_ids", [])}
    return [g for g in prioriser(gaps) if g["gap_id"] not in visees]

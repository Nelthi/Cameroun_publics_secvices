"""Faux fichiers pour tester T2 seule (règle d'or du guide : on simule les entrées des autres).

- audit.db factice : table gaps (10 lacunes inventées) + table audit_log ;
- eval_report.json factice au format du contrat de T1 (6 échecs, tous les cas de figure) ;
- questions.json factice (texte de quelques questions de T1).

    python -m gaps.mocks gaps/examples      # écrit les fichiers dans ce dossier
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROUTING_CNI = {"domain": "public_services", "subdomain": "national_identity_card"}

# (request_id, question, routage, sujet de la lacune, raison, date)
MOCK_GAP_ROWS = [
    ("REQ-20261110-0001", "Combien coûte le permis de conduire ?", {"domain": "public_services", "subdomain": "driving_license"}, "coût du permis", "no_relevant_chunk", "2026-11-10T09:00:00"),
    ("REQ-20261110-0002", "Quels sont les frais du permis de conduire ?", {"domain": "public_services"}, "frais du permis de conduire", "no_relevant_chunk", "2026-11-10T09:30:00"),
    ("REQ-20261110-0003", "Quels sont les frais pour la CNI ?", ROUTING_CNI, "frais CNI", "no_relevant_chunk", "2026-11-10T10:00:00"),
    ("REQ-20261110-0004", "Quel est le coût de la carte nationale d'identité ?", ROUTING_CNI, "coût de la carte nationale d'identité", "low_score", "2026-11-10T10:30:00"),
    ("REQ-20261110-0005", "frais cni svp", ROUTING_CNI, "frais CNI", "no_relevant_chunk", "2026-11-10T11:00:00"),
    ("REQ-20261110-0006", "Quel est le délai pour avoir mon passeport ?", {"domain": "public_services"}, "délai de délivrance du passeport", "no_relevant_chunk", "2026-11-10T11:30:00"),
    ("REQ-20261110-0007", "Comment obtenir une copie intégrale d'acte de naissance ?", {"domain": "public_services"}, "acte de naissance copie intégrale", "no_relevant_chunk", "2026-11-10T12:00:00"),
    ("REQ-20261110-0008", "Quand déclarer mes impôts sur le revenu ?", {"domain": "public_services"}, "impôt sur le revenu : délais de déclaration", "no_relevant_chunk", "2026-11-10T12:30:00"),
    ("REQ-20261110-0009", "Mes données sont-elles protégées par la loi ?", {"domain": "public_services"}, "loi sur les données personnelles", "no_relevant_chunk", "2026-11-10T13:00:00"),
    ("REQ-20261110-0010", "Mon numéro est le 655123456, combien coûte la CNI ?", ROUTING_CNI, "frais CNI", "no_relevant_chunk", "2026-11-10T13:30:00"),
]

MOCK_EVAL_REPORT = {
    "run_id": "EVAL-20261112-01",
    "n_questions": 25,
    "metrics": {"source_hit_rate": 0.84, "correct_refusal_rate": 0.9, "avg_duration_ms": 4200},
    "failures": [
        # source attendue, refus obtenu, et l'audit a déjà une lacune pour cette requête (à ne pas recompter)
        {"question_id": "Q03", "expected": {"document_id": "DOC-MOCKCNI", "page": 2}, "got": "refused", "request_id": "REQ-20261110-0003"},
        # refus attendu mais réponse donnée : problème de garde-fous, pas un document manquant
        {"question_id": "Q07", "expected": "refused", "got": "approved", "request_id": "REQ-20261112-0007"},
        # mauvaise source ; texte de la question seulement dans questions.json
        {"question_id": "Q11", "expected": {"document_id": "DOC-MOCKCNI", "page": 1}, "got": "approved", "request_id": "REQ-20261112-0011"},
        # réponse partielle, même sujet que « coût du permis »
        {"question_id": "Q15", "expected": {"document_id": "DOC-MOCKPERMIS", "page": 1}, "got": "partial", "request_id": "REQ-20261112-0015"},
        # refus, sans request_id
        {"question_id": "Q19", "expected": {"document_id": "DOC-MOCKPASS", "page": 3}, "got": "refused", "request_id": None},
        # texte de la question introuvable : écarté
        {"question_id": "Q22", "expected": {"document_id": "DOC-MOCKCNI", "page": 2}, "got": "refused", "request_id": "REQ-20261112-0022"},
    ],
}

MOCK_QUESTIONS = [
    {"id": "Q11", "question": "Quels documents pour le renouvellement de la CNI ?"},
    {"id": "Q15", "question": "Combien coûte le permis de conduire pour un étudiant ?"},
    {"id": "Q19", "question": "Où déposer ma demande de passeport ?"},
]


def write_mock_audit_db(path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE audit_log (request_id TEXT PRIMARY KEY, created_at TEXT, question TEXT, "
                     "routing TEXT, status TEXT)")
        conn.execute("CREATE TABLE gaps (id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT, topic TEXT, "
                     "reason TEXT, created_at TEXT)")
        for request_id, question, routing, topic, reason, when in MOCK_GAP_ROWS:
            conn.execute("INSERT INTO audit_log VALUES (?,?,?,?,?)",
                         (request_id, when, question, json.dumps(routing), "refused"))
            conn.execute("INSERT INTO gaps (request_id, topic, reason, created_at) VALUES (?,?,?,?)",
                         (request_id, topic, reason, when))
        conn.commit()
    finally:
        conn.close()
    return path


def write_mock_files(directory: str | Path) -> dict[str, Path]:
    """Écrit les trois faux fichiers dans `directory` et renvoie leurs chemins."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "audit_db": write_mock_audit_db(directory / "mock_audit.db"),
        "eval_report": directory / "mock_eval_report.json",
        "questions": directory / "mock_questions.json",
    }
    paths["eval_report"].write_text(json.dumps(MOCK_EVAL_REPORT, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths["questions"].write_text(json.dumps(MOCK_QUESTIONS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return paths


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("gaps/examples")
    for name, p in write_mock_files(target).items():
        print(f"{name}: {p}")

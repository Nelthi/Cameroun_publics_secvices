"""Lecture et validation des fichiers de fragments produits par T3.

Contrat attendu (data/chunks/{document_id}.json) :
{
  "document_id": "DOC-A1B2C3D4",
  "chunks": [
    {"chunk_id": "DOC-A1B2C3D4-C001", "text": "...", "source_page": 1, "position": 0}
  ]
}
"""
import json
from pathlib import Path

from .config import CHUNKS_DIR

REQUIRED_CHUNK_FIELDS = ("chunk_id", "text", "source_page")


def load_chunks(chunks_dir=CHUNKS_DIR):
    """Charge tous les *.json du dossier et renvoie une liste PLATE de fragments.

    Chaque élément : {"chunk_id", "document_id", "text", "source_page"}.
    - Les fragments au texte vide sont ignorés.
    - Les chunk_id en double sont ignorés (on garde le premier).
    - Un fichier mal formé lève une ValueError qui dit quel fichier et quoi.
    """
    chunks_dir = Path(chunks_dir)
    files = sorted(chunks_dir.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"Aucun fichier .json de fragments dans {chunks_dir}")

    chunks, seen = [], set()
    for file in files:
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{file.name} : JSON invalide ({exc})") from exc
        chunks.extend(_parse_document(data, file.name, seen))

    if not chunks:
        raise ValueError(f"Aucun fragment exploitable dans {chunks_dir}")
    return chunks


def _parse_document(data, filename, seen):
    if not isinstance(data, dict) or "document_id" not in data:
        raise ValueError(f"{filename} : champ 'document_id' manquant")
    if not isinstance(data.get("chunks"), list):
        raise ValueError(f"{filename} : champ 'chunks' manquant ou n'est pas une liste")

    result = []
    for i, chunk in enumerate(data["chunks"]):
        for field in REQUIRED_CHUNK_FIELDS:
            if field not in chunk:
                raise ValueError(f"{filename} : fragment n°{i} sans champ '{field}'")
        text = str(chunk["text"]).strip()
        if not text or chunk["chunk_id"] in seen:
            continue
        seen.add(chunk["chunk_id"])
        result.append({
            "chunk_id": chunk["chunk_id"],
            "document_id": data["document_id"],
            "text": text,
            "source_page": chunk["source_page"],
        })
    return result

"""Vérification du contrat de sortie T3 (utilisée par la commande et par validate.py)."""

TOP_FIELDS = {"document_id", "chunk_size", "chunk_overlap", "chunks"}
CHUNK_FIELDS = {"chunk_id", "text", "source_page", "position"}


def validate_output(data):
    """Retourne la liste des erreurs (liste vide = contrat respecté)."""
    errors = []
    if not isinstance(data, dict):
        return ["la racine doit être un objet JSON"]
    if set(data) != TOP_FIELDS:
        return [f"les champs de premier niveau doivent être exactement {sorted(TOP_FIELDS)}, reçu {sorted(data)}"]
    doc_id, size = data["document_id"], data["chunk_size"]
    if not isinstance(doc_id, str) or not doc_id:
        errors.append("document_id doit être une chaîne non vide")
    if not isinstance(size, int) or not isinstance(data["chunk_overlap"], int):
        return errors + ["chunk_size et chunk_overlap doivent être des entiers"]
    if not isinstance(data["chunks"], list):
        return errors + ["chunks doit être une liste"]
    seen = set()
    for i, c in enumerate(data["chunks"]):
        where = f"chunks[{i}]"
        if not isinstance(c, dict) or set(c) != CHUNK_FIELDS:
            errors.append(f"{where} : les champs doivent être exactement {sorted(CHUNK_FIELDS)}")
            continue
        if c["chunk_id"] != f"{doc_id}-C{i + 1:03d}":
            errors.append(f"{where} : chunk_id inattendu {c['chunk_id']!r}")
        if c["chunk_id"] in seen:
            errors.append(f"{where} : chunk_id en double")
        seen.add(c["chunk_id"])
        if not isinstance(c["text"], str) or not c["text"].strip():
            errors.append(f"{where} : text doit être une chaîne non vide")
        elif len(c["text"]) > size:
            errors.append(f"{where} : text fait {len(c['text'])} caractères (> {size})")
        if not isinstance(c["source_page"], int) or c["source_page"] < 1:
            errors.append(f"{where} : source_page doit être un entier >= 1")
        if c["position"] != i:
            errors.append(f"{where} : position doit valoir {i}")
    return errors

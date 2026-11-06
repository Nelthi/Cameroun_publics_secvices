"""Logique de découpage (chunking) de T3.

Entrée : le JSON produit par T2 (document_id + pages[]).
Sortie : un dictionnaire conforme au contrat T3 (voir README.md).
"""
import bisect
import re

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
_SENT_END = re.compile(r"[.;!?](?=\s|$)")


def _build_text(pages):
    """Colle les pages (séparées par une ligne vide) et mémorise où commence chaque page.

    Retourne (texte_complet, offsets_de_début_de_page, numéros_de_page).
    Les pages vides sont ignorées.
    """
    parts, starts, numbers, pos = [], [], [], 0
    for p in sorted(pages, key=lambda p: p["page_number"]):
        text = (p.get("text") or "").strip()
        if not text:
            continue
        if parts:
            pos += 2  # le séparateur "\n\n"
        starts.append(pos)
        numbers.append(p["page_number"])
        parts.append(text)
        pos += len(text)
    return "\n\n".join(parts), starts, numbers


def _find_cut(text, start, size):
    """Retourne la position de fin du fragment qui commence à `start`.

    Ordre de préférence : dernière fin de phrase, puis dernier espace,
    puis coupe dure (mot géant). Les coupes dans la première moitié de la
    fenêtre sont ignorées pour éviter des fragments minuscules.
    """
    end = start + size
    if end >= len(text):
        return len(text)
    window = text[start:end + 1]
    lo = size // 2
    last = None
    for m in _SENT_END.finditer(window):
        if m.end() >= lo:
            last = m.end()
    if last and last <= size:
        return start + last
    ws = max(window.rfind(" "), window.rfind("\n"), window.rfind("\t"))
    if ws >= lo:
        return start + ws
    return end


def chunk_pages(pages, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Découpe les pages en tuples (texte, page_de_départ)."""
    if overlap >= chunk_size:
        raise ValueError("le chevauchement doit être inférieur à la taille des fragments")
    text, starts, numbers = _build_text(pages)
    chunks, start = [], 0
    while start < len(text):
        end = _find_cut(text, start, chunk_size)
        raw = text[start:end]
        piece = raw.strip()
        if piece:
            lead = len(raw) - len(raw.lstrip())
            idx = bisect.bisect_right(starts, start + lead) - 1
            chunks.append((piece, numbers[max(idx, 0)]))
        if end >= len(text):
            break
        nxt = k = end - overlap
        while k < end and not text[k - 1].isspace():
            k += 1  # ne jamais commencer le fragment suivant au milieu d'un mot
        if k < end:
            nxt = k
        # sinon : un seul mot géant, coupe dure avec chevauchement brut
        start = max(nxt, start + 1)
    return chunks


def chunk_document(doc, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Construit le dictionnaire de sortie T3 à partir d'un document T2."""
    doc_id = doc["document_id"]
    return {
        "document_id": doc_id,
        "chunk_size": chunk_size,
        "chunk_overlap": overlap,
        "chunks": [
            {"chunk_id": f"{doc_id}-C{i + 1:03d}", "text": t, "source_page": pg, "position": i}
            for i, (t, pg) in enumerate(chunk_pages(doc["pages"], chunk_size, overlap))
        ],
    }

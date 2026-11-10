"""Découpage SÉMANTIQUE par agent IA (Groq) : seconde méthode, à côté du découpeur d'Alex.

`chunking/core.py` (Alex) reste la méthode « code natif » ; ce module ne le remplace pas.
Même contrat de sortie (`chunking.contract.validate_output`) : on peut donc choisir l'une
ou l'autre sans rien changer en aval (T4 vectorisation, recherche, agents).

Principe — le modèle ne réécrit JAMAIS le texte :
  1. le code découpe chaque page en petites unités (phrases / paragraphes) numérotées ;
  2. l'IA indique seulement À QUELLES UNITÉS COMMENCE chaque nouveau fragment (une idée,
     une étape, une rubrique par fragment) ;
  3. le code reconstitue les fragments depuis le texte d'origine, donc sans invention ni
     déformation, et impose la taille maximale (800 caractères) et la page exacte.

Différences avec le découpage natif : un fragment ne chevauche pas deux pages (source_page
toujours exacte) et il n'y a pas de recouvrement (chunk_overlap = 0).

    from chunking.ai_chunker import chunk_document_ai
    result = chunk_document_ai(entrée_T3)      # même format que chunk_document
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from .contract import validate_output
from .core import CHUNK_SIZE

WINDOW_CHARS = 6000  # taille de texte envoyée à l'IA par appel
_BOUNDARY = re.compile(r"(?<=[.;!?])\s+|\n\s*\n")

PROMPT = """Tu prépares des documents administratifs pour un moteur de recherche (RAG).
Voici le texte d'une page, déjà découpé en unités numérotées (phrases ou paragraphes).
Regroupe des unités CONSÉCUTIVES en fragments cohérents : chaque fragment doit traiter d'UN seul
sujet, d'UNE seule étape ou d'UNE seule rubrique (une procédure, une liste de pièces, un tarif,
un délai, une adresse...) et pouvoir se comprendre seul. Ne sépare pas un titre de son contenu,
ni une liste de son introduction. Un fragment ne doit pas dépasser {limit} caractères au total
(la longueur de chaque unité est indiquée). Ne réordonne rien et n'omets aucune unité.

Réponds UNIQUEMENT par un objet JSON de la forme {{"starts": [0, 4, 9]}} où "starts" liste le
numéro de la PREMIÈRE unité de chaque fragment, dans l'ordre croissant, en commençant par 0.

UNITÉS :
{units}
"""


class AIChunkingError(RuntimeError):
    """L'appel à l'IA a échoué (clé absente, quota, réseau...). Rien n'est produit en silence."""


def _units(page_text: str, limit: int):
    """Découpe une page en unités (début, fin) dans page_text, chacune de longueur <= limit."""
    spans, pos = [], 0
    for match in _BOUNDARY.finditer(page_text):
        spans.append((pos, match.start()))
        pos = match.end()
    spans.append((pos, len(page_text)))
    units = []
    for start, end in spans:
        while end > start and page_text[start:end].strip() == "":
            end = start  # unité vide
        if end <= start:
            continue
        while end - start > limit:  # unité trop longue : coupe à un espace
            cut = page_text.rfind(" ", start + limit // 2, start + limit)
            cut = cut if cut != -1 else start + limit
            units.append((start, cut))
            start = cut + 1 if page_text[cut:cut + 1] == " " else cut
        if page_text[start:end].strip():
            units.append((start, end))
    return units


def _windows(units, text):
    window, size = [], 0
    for unit in units:
        length = unit[1] - unit[0]
        if window and size + length > WINDOW_CHARS:
            yield window
            window, size = [], 0
        window.append(unit)
        size += length
    if window:
        yield window


def _greedy_starts(window, limit):
    """Découpe de secours : remplit chaque fragment jusqu'à `limit` (sans IA)."""
    starts, begin = [0], window[0][0]
    for i, (_, end) in enumerate(window):
        if end - begin > limit and i > 0 and (not starts or starts[-1] != i):
            starts.append(i)
            begin = window[i][0]
    return starts


def _clean_starts(raw, count):
    """Valide la réponse de l'IA ; renvoie None si elle est inexploitable."""
    if not isinstance(raw, dict) or not isinstance(raw.get("starts"), list):
        return None
    try:
        starts = sorted({int(x) for x in raw["starts"] if 0 <= int(x) < count})
    except (TypeError, ValueError):
        return None
    if not starts:
        return None
    return starts if starts[0] == 0 else [0] + starts


def _groups(window, starts, limit, text):
    """Transforme les débuts de fragments en spans (début, fin) <= limit, en respectant la taille."""
    bounds = starts + [len(window)]
    spans = []
    for a, b in zip(bounds, bounds[1:]):
        group = window[a:b]
        begin = group[0][0]
        last_end = group[0][1]
        for start, end in group[1:]:
            if end - begin > limit:  # l'IA a dépassé la taille : on coupe ici
                spans.append((begin, last_end))
                begin = start
            last_end = end
        spans.append((begin, last_end))
    return spans


def chunk_document_ai(doc: dict, chunk_size: int = CHUNK_SIZE, *, ask: Optional[Callable[[str], str]] = None,
                      report: Optional[dict] = None) -> dict:
    """Découpe un document (`{"document_id", "pages": [{"page_number", "text"}]}`) avec l'IA.

    `ask(prompt) -> str` : fonction d'appel au modèle (par défaut Groq, modèle de qualité).
    `report` : dictionnaire optionnel rempli avec model, llm_calls, fallback_windows.
    """
    from backend.ai import groq

    if ask is None:
        model = groq.quality_model()

        def ask(prompt: str) -> str:  # noqa: F811
            return groq.ask(prompt, model=model)
    else:
        model = getattr(ask, "model", "personnalisé")
    stats = report if report is not None else {}
    stats.update({"model": model, "llm_calls": 0, "fallback_windows": 0, "pages": 0})

    chunks = []
    for page in doc["pages"]:
        text, number = page["text"], page["page_number"]
        units = _units(text, chunk_size)
        if not units:
            continue
        stats["pages"] += 1
        for window in _windows(units, text):
            if len(window) == 1:
                starts = [0]
            else:
                listing = "\n".join(
                    f"[{i}] ({end - start} car.) {' '.join(text[start:end].split())}"
                    for i, (start, end) in enumerate(window))
                try:
                    answer = ask(PROMPT.format(limit=chunk_size, units=listing))
                except Exception as exc:  # noqa: BLE001
                    raise AIChunkingError(f"{type(exc).__name__}: {exc}") from exc
                stats["llm_calls"] += 1
                from backend.ai.groq import parse_json

                try:
                    starts = _clean_starts(parse_json(answer), len(window))
                except ValueError:
                    starts = None
                if starts is None:  # réponse illisible : découpe de secours, signalée dans le rapport
                    stats["fallback_windows"] += 1
                    starts = _greedy_starts(window, chunk_size)
            for begin, end in _groups(window, starts, chunk_size, text):
                piece = text[begin:end].strip()
                if piece:
                    chunks.append({"text": piece, "source_page": number})

    doc_id = doc["document_id"]
    result = {
        "document_id": doc_id,
        "chunk_size": chunk_size,
        "chunk_overlap": 0,
        "chunks": [
            {"chunk_id": f"{doc_id}-C{i + 1:03d}", "text": c["text"],
             "source_page": c["source_page"], "position": i}
            for i, c in enumerate(chunks)
        ],
    }
    errors = validate_output(result)
    if errors:
        raise ValueError("Sortie du découpage IA hors contrat : " + " ; ".join(errors))
    return result

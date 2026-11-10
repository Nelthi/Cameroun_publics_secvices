"""Pré-remplissage des métadonnées d'un document (titre, institution, date, domaine...) avec Groq.

L'IA lit le nom du fichier et le début du document (titre ou premier paragraphe) et propose les
champs exigés par T1. Sans clé Groq, une proposition simple (sans IA) est renvoyée et signalée
(`ai: false`) : l'administrateur peut toujours corriger avant l'envoi.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Callable, Iterable, Optional

from . import groq

EXCERPT_CHARS = 1800

PROMPT = """Tu aides à cataloguer des documents officiels camerounais (services publics).
À partir du nom de fichier et du début du document, propose ses métadonnées.

Nom du fichier : {filename}
Début du document :
\"\"\"
{excerpt}
\"\"\"

Sous-domaines déjà utilisés (réutilise-en un si le sujet correspond) : {known}

Réponds UNIQUEMENT par un objet JSON avec ces clés :
- "title" : titre clair du document (en français, sans le mot « fichier »)
- "institution" : institution émettrice (ex. DGSN, Ministère de la Justice) ; "" si inconnue
- "date" : date du document au format AAAA-MM-JJ ; "" si elle n'apparaît pas
- "domain" : "public_services" sauf si le document relève clairement d'un autre grand domaine
- "subdomain" : thème en snake_case anglais, court (ex. national_identity_card, passport, birth_certificate)
- "summary" : une phrase résumant le document
"""


def extract_excerpt(path, limit: int = EXCERPT_CHARS) -> str:
    """Début du texte d'un fichier PDF, DOCX ou TXT (premiers paragraphes)."""
    path = Path(path)
    suffix = path.suffix.lower()
    text = ""
    try:
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(path), strict=False)
            for page in reader.pages[:3]:
                text += (page.extract_text() or "") + "\n"
                if len(text) >= limit:
                    break
        elif suffix == ".docx":
            from docx import Document

            text = "\n".join(p.text for p in Document(str(path)).paragraphs[:40])
        else:
            text = path.read_text(encoding="utf-8", errors="replace")[: limit * 2]
    except Exception:  # noqa: BLE001 - un fichier illisible ne doit pas bloquer l'envoi
        return ""
    return re.sub(r"[ \t]+", " ", text).strip()[:limit]


def _slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _valid_date(value: str) -> str:
    try:
        return date.fromisoformat((value or "").strip()[:10]).isoformat()
    except ValueError:
        return ""


def heuristic(filename: str, excerpt: str) -> dict:
    first = next((line.strip() for line in excerpt.splitlines() if len(line.strip()) > 8), "")
    title = first[:120] or Path(filename).stem.replace("_", " ").replace("-", " ").strip() or filename
    return {"title": title, "institution": "", "date": date.today().isoformat(), "domain": "public_services",
            "subdomain": _slug(Path(filename).stem)[:40] or "general", "summary": "", "date_guessed": True}


def suggest_metadata(filename: str, excerpt: str, known_subdomains: Iterable[str] = (),
                     ask: Optional[Callable[[str], str]] = None) -> dict:
    """Renvoie {title, institution, date, domain, subdomain, summary, ai, date_guessed, warning?}."""
    base = heuristic(filename, excerpt)
    if ask is None:
        if not groq.is_configured():
            return {**base, "ai": False, "warning": "GROQ_API_KEY absente : proposition sans IA."}
        ask = lambda prompt: groq.ask(prompt, model=groq.fast_model(), fallback_model=groq.quality_model())  # noqa: E731
    prompt = PROMPT.format(filename=filename, excerpt=excerpt or "(texte non lisible)",
                           known=", ".join(sorted(set(known_subdomains))) or "aucun")
    try:
        data = groq.parse_json(ask(prompt))
        if not isinstance(data, dict):
            raise ValueError("réponse non structurée")
    except Exception as exc:  # noqa: BLE001
        return {**base, "ai": False, "warning": f"Groq indisponible ({type(exc).__name__}) : proposition sans IA."}
    found_date = _valid_date(str(data.get("date", "")))
    return {
        "title": str(data.get("title") or base["title"]).strip()[:160],
        "institution": str(data.get("institution") or "").strip()[:120],
        "date": found_date or base["date"],
        "date_guessed": not found_date,
        "domain": _slug(str(data.get("domain") or "")) or "public_services",
        "subdomain": _slug(str(data.get("subdomain") or "")) or base["subdomain"],
        "summary": str(data.get("summary") or "").strip()[:300],
        "ai": True,
    }

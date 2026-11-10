"""Client Groq (API compatible OpenAI, endpoint « responses »).

Configuration (variables d'environnement) :
    GROQ_API_KEY        clé créée sur https://console.groq.com  (obligatoire)
    GROQ_MODEL          modèle « qualité » (défaut : openai/gpt-oss-120b)
    GROQ_FAST_MODEL     modèle « rapide » (défaut : openai/gpt-oss-20b)

Choix des modèles, d'après la fiche « Supported Models » de GroqCloud :
  * les Llama (3.1 8B, 3.3 70B), Muse Spark et MiniMax sont marqués « Enterprise / Contact Sales » :
    non utilisables en libre-service ;
  * Qwen 3.8 est en « Preview » (à ne pas utiliser en production) ;
  * il reste openai/gpt-oss-120b (le plus capable, 131 072 tokens de contexte, 65 536 de sortie)
    et openai/gpt-oss-20b (le plus rapide, ~1000 tokens/s, moins cher).
  Le 120B sert au découpage sémantique (qualité), le 20B aux tâches courtes (métadonnées) et de
  secours si le 120B est indisponible ou limité en débit.
"""
from __future__ import annotations

import json
import os
import re
from typing import Callable, Optional

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_FAST_MODEL = "openai/gpt-oss-20b"


class GroqNotConfiguredError(RuntimeError):
    """GROQ_API_KEY absente."""


class GroqError(RuntimeError):
    """Échec d'appel à Groq (réseau, quota, modèle indisponible...)."""


def quality_model() -> str:
    return os.getenv("GROQ_MODEL", DEFAULT_MODEL)


def fast_model() -> str:
    return os.getenv("GROQ_FAST_MODEL", DEFAULT_FAST_MODEL)


def is_configured() -> bool:
    return bool(os.getenv("GROQ_API_KEY"))


def get_client():
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise GroqNotConfiguredError(
            "GROQ_API_KEY absente : créez une clé sur console.groq.com puis "
            "`export GROQ_API_KEY=...` avant de lancer le serveur."
        )
    from openai import OpenAI

    return OpenAI(api_key=key, base_url=GROQ_BASE_URL, timeout=90, max_retries=2)


def ask(prompt: str, *, model: Optional[str] = None, fallback_model: Optional[str] = None,
        client=None) -> str:
    """Envoie `prompt` et renvoie le texte. Essaie `model`, puis `fallback_model`."""
    client = client or get_client()
    models = [m for m in (model or quality_model(), fallback_model or fast_model()) if m]
    models = list(dict.fromkeys(models))  # sans doublon, ordre conservé
    last: Optional[Exception] = None
    for name in models:
        try:
            response = client.responses.create(input=prompt, model=name)
            text = (response.output_text or "").strip()
            if text:
                return text
            last = GroqError(f"réponse vide du modèle {name}")
        except Exception as exc:  # noqa: BLE001 - on tente le modèle suivant
            last = exc
    raise GroqError(f"Appel Groq impossible ({', '.join(models)}) : {last}") from last


def parse_json(text: str):
    """Extrait le premier objet ou tableau JSON d'une réponse (ignore ``` et texte autour)."""
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = cleaned.find(opener), cleaned.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("aucun JSON exploitable dans la réponse du modèle")


AskFn = Callable[[str], str]

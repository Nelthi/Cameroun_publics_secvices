"""Point d'entrée LLM unique de la Phase 3 : llm_generate(prompt) -> texte.

Le choix du LLM reste à décider en équipe : il est caché derrière cette fonction.
Aucun fournisseur n'est imposé ; on configure par variables d'environnement.

Fournisseur « openai_compatible » (OpenAI, Ollama, vLLM, Groq, LM Studio...) :
    export LLM_PROVIDER=openai_compatible
    export LLM_MODEL=<nom du modèle>
    export LLM_BASE_URL=http://localhost:11434/v1     # défaut : https://api.openai.com/v1
    export LLM_API_KEY=<clé>                          # facultatif pour un serveur local

Fournisseur « anthropic » (API Messages de Claude) :
    export LLM_PROVIDER=anthropic
    export LLM_MODEL=<nom du modèle>
    export LLM_API_KEY=<clé>

Réglages facultatifs : LLM_TEMPERATURE (0.0), LLM_MAX_TOKENS (700), LLM_TIMEOUT (60),
LLM_MAX_RETRIES (2).

Pour les tests ou pour brancher un autre moteur : set_llm(ma_fonction).
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Callable

import httpx

from .exceptions import LLMError, LLMNotConfiguredError

logger = logging.getLogger(__name__)

PROVIDERS = ("openai_compatible", "anthropic")
ANTHROPIC_VERSION = "2023-06-01"

_override: Callable[[str], str] | None = None
_transport: httpx.BaseTransport | None = None  # injectable dans les tests


def set_llm(function: Callable[[str], str] | None) -> None:
    """Remplace llm_generate par `function` (None pour revenir à la configuration par défaut)."""
    global _override
    _override = function


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    api_key: str
    base_url: str
    temperature: float
    max_tokens: int
    timeout: float
    max_retries: int

    @classmethod
    def from_env(cls) -> "LLMConfig":
        env = os.environ
        provider = env.get("LLM_PROVIDER", "").strip().lower()
        if not provider:
            raise LLMNotConfiguredError(
                "Aucun LLM configuré. Définissez LLM_PROVIDER (openai_compatible ou anthropic), "
                "LLM_MODEL et, si besoin, LLM_API_KEY / LLM_BASE_URL (voir backend/agents/llm.py)."
            )
        if provider not in PROVIDERS:
            raise LLMNotConfiguredError(f"LLM_PROVIDER '{provider}' inconnu. Valeurs : {', '.join(PROVIDERS)}.")
        model = env.get("LLM_MODEL", "").strip()
        if not model:
            raise LLMNotConfiguredError("LLM_MODEL n'est pas défini.")
        api_key = env.get("LLM_API_KEY", "").strip()
        if provider == "anthropic" and not api_key:
            raise LLMNotConfiguredError("LLM_API_KEY est obligatoire pour le fournisseur anthropic.")
        default_url = "https://api.anthropic.com" if provider == "anthropic" else "https://api.openai.com/v1"
        try:
            return cls(
                provider=provider,
                model=model,
                api_key=api_key,
                base_url=env.get("LLM_BASE_URL", "").strip().rstrip("/") or default_url,
                temperature=float(env.get("LLM_TEMPERATURE", "0.0")),
                max_tokens=int(env.get("LLM_MAX_TOKENS", "700")),
                timeout=float(env.get("LLM_TIMEOUT", "60")),
                max_retries=int(env.get("LLM_MAX_RETRIES", "2")),
            )
        except ValueError as exc:
            raise LLMNotConfiguredError(f"Réglage LLM_* numérique invalide : {exc}") from exc


def llm_generate(prompt: str) -> str:
    """Envoie `prompt` au LLM configuré et renvoie le texte généré (jamais vide)."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Le prompt ne peut pas être vide")
    if _override is not None:
        text = _override(prompt)
    else:
        config = LLMConfig.from_env()
        text = _call_anthropic(prompt, config) if config.provider == "anthropic" else _call_openai(prompt, config)
    if not isinstance(text, str) or not text.strip():
        raise LLMError("Le LLM a renvoyé une réponse vide")
    return text.strip()


def _post_with_retries(url: str, headers: dict, payload: dict, config: LLMConfig) -> dict:
    """POST JSON avec nouvelles tentatives (réseau, 429, 5xx). Ne journalise jamais la clé."""
    last_error = "inconnue"
    with httpx.Client(timeout=config.timeout, transport=_transport) as client:
        for attempt in range(config.max_retries + 1):
            try:
                response = client.post(url, headers=headers, json=payload)
            except httpx.TransportError as exc:  # inclut les timeouts
                last_error = f"erreur réseau : {type(exc).__name__}"
            else:
                if response.status_code == 429 or response.status_code >= 500:
                    last_error = f"HTTP {response.status_code}"
                elif response.status_code >= 400:
                    raise LLMError(f"Le LLM a refusé la requête (HTTP {response.status_code}) : {response.text[:300]}")
                else:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise LLMError("Réponse du LLM illisible (JSON invalide)") from exc
            if attempt < config.max_retries:
                delay = 2**attempt
                logger.warning("LLM indisponible (%s), nouvelle tentative dans %ss", last_error, delay)
                time.sleep(delay)
    raise LLMError(f"LLM indisponible après {config.max_retries + 1} tentative(s) ({last_error})")


def _call_openai(prompt: str, config: LLMConfig) -> str:
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    payload = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }
    data = _post_with_retries(f"{config.base_url}/chat/completions", headers, payload, config)
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("Format de réponse inattendu (openai_compatible)") from exc


def _call_anthropic(prompt: str, config: LLMConfig) -> str:
    headers = {
        "Content-Type": "application/json",
        "x-api-key": config.api_key,
        "anthropic-version": ANTHROPIC_VERSION,
    }
    payload = {
        "model": config.model,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    data = _post_with_retries(f"{config.base_url}/v1/messages", headers, payload, config)
    try:
        blocks = data["content"]
        return "".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text")
    except (KeyError, TypeError) as exc:
        raise LLMError("Format de réponse inattendu (anthropic)") from exc

"""Configuration T1 Phase 4 — aucune URL ni secret en dur dans le code métier.

Les valeurs viennent exclusivement de l'environnement (voir .env.example).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or not str(value).strip():
        return default
    return str(value).strip()


@dataclass(frozen=True)
class EvalConfig:
    """Paramètres runtime de l'évaluateur."""

    api_base_url: str
    ask_path: str
    http_timeout_seconds: float
    ask_mode: str  # "http" | "mock"

    @property
    def ask_url(self) -> str:
        base = self.api_base_url.rstrip("/")
        path = self.ask_path if self.ask_path.startswith("/") else f"/{self.ask_path}"
        return f"{base}{path}"


def load_config() -> EvalConfig:
    """Charge la configuration depuis l'environnement."""
    timeout_raw = _env("EVAL_HTTP_TIMEOUT_SECONDS", "30")
    try:
        timeout = float(timeout_raw)
    except ValueError as exc:
        raise ValueError(
            "EVAL_HTTP_TIMEOUT_SECONDS doit être un nombre (ex. 30)."
        ) from exc
    if timeout <= 0:
        raise ValueError("EVAL_HTTP_TIMEOUT_SECONDS doit être > 0.")

    mode = _env("EVAL_ASK_MODE", "mock").lower()
    if mode not in {"http", "mock"}:
        raise ValueError("EVAL_ASK_MODE doit valoir 'http' ou 'mock'.")

    return EvalConfig(
        api_base_url=_env("EVAL_API_BASE_URL", "http://127.0.0.1:8000"),
        ask_path=_env("EVAL_ASK_PATH", "/ask"),
        http_timeout_seconds=timeout,
        ask_mode=mode,
    )

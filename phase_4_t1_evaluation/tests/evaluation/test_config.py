"""Tests Étape 0 — configuration (env, pas de secrets en dur)."""

from __future__ import annotations

import pytest

from evaluation.config import load_config


def test_load_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EVAL_API_BASE_URL", raising=False)
    monkeypatch.delenv("EVAL_HTTP_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("EVAL_ASK_PATH", raising=False)
    monkeypatch.delenv("EVAL_ASK_MODE", raising=False)

    cfg = load_config()
    assert cfg.api_base_url == "http://127.0.0.1:8000"
    assert cfg.ask_path == "/ask"
    assert cfg.ask_url == "http://127.0.0.1:8000/ask"
    assert cfg.http_timeout_seconds == 30.0
    assert cfg.ask_mode == "mock"


def test_load_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVAL_API_BASE_URL", "http://example.test:9000/")
    monkeypatch.setenv("EVAL_ASK_PATH", "ask")
    monkeypatch.setenv("EVAL_HTTP_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("EVAL_ASK_MODE", "http")

    cfg = load_config()
    assert cfg.ask_url == "http://example.test:9000/ask"
    assert cfg.http_timeout_seconds == 12.5
    assert cfg.ask_mode == "http"


def test_invalid_timeout_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVAL_HTTP_TIMEOUT_SECONDS", "abc")
    with pytest.raises(ValueError):
        load_config()


def test_invalid_mode_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVAL_ASK_MODE", "ftp")
    with pytest.raises(ValueError):
        load_config()

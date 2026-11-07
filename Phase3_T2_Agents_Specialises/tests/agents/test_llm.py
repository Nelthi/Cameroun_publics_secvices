import json

import httpx
import pytest

from backend.agents import llm as llm_module
from backend.agents.exceptions import LLMError, LLMNotConfiguredError
from backend.agents.llm import llm_generate, set_llm


def _use(monkeypatch, handler):
    monkeypatch.setattr(llm_module, "_transport", httpx.MockTransport(handler))
    monkeypatch.setattr(llm_module.time, "sleep", lambda s: None)


def test_not_configured():
    with pytest.raises(LLMNotConfiguredError, match="LLM_PROVIDER"):
        llm_generate("bonjour")


def test_unknown_provider_and_missing_model(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "foo")
    with pytest.raises(LLMNotConfiguredError, match="inconnu"):
        llm_generate("x")
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    with pytest.raises(LLMNotConfiguredError, match="LLM_MODEL"):
        llm_generate("x")


def test_anthropic_requires_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "m")
    with pytest.raises(LLMNotConfiguredError, match="LLM_API_KEY"):
        llm_generate("x")


def test_empty_prompt_rejected():
    set_llm(lambda p: "ok")
    with pytest.raises(ValueError):
        llm_generate("   ")


def test_override_and_empty_answer():
    set_llm(lambda p: "  réponse  ")
    assert llm_generate("q") == "réponse"
    set_llm(lambda p: "   ")
    with pytest.raises(LLMError, match="vide"):
        llm_generate("q")


def test_openai_compatible_request_and_parsing(monkeypatch):
    seen = {}

    def handler(request):
        seen["url"], seen["auth"] = str(request.url), request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": " Bonjour [1] "}}]})

    _use(monkeypatch, handler)
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_MODEL", "mon-modele")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1/")
    monkeypatch.setenv("LLM_API_KEY", "secret")
    assert llm_generate("Question ?") == "Bonjour [1]"
    assert seen["url"] == "http://localhost:11434/v1/chat/completions"
    assert seen["auth"] == "Bearer secret"
    assert seen["body"]["model"] == "mon-modele" and seen["body"]["temperature"] == 0.0
    assert seen["body"]["messages"] == [{"role": "user", "content": "Question ?"}]


def test_openai_compatible_without_key_sends_no_auth(monkeypatch):
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    _use(monkeypatch, handler)
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_MODEL", "m")
    llm_generate("x")
    assert seen["auth"] is None


def test_anthropic_request_and_parsing(monkeypatch):
    seen = {}

    def handler(request):
        seen["url"], seen["key"] = str(request.url), request.headers.get("x-api-key")
        seen["version"] = request.headers.get("anthropic-version")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"content": [{"type": "text", "text": "Salut "}, {"type": "text", "text": "[2]"}]})

    _use(monkeypatch, handler)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("LLM_API_KEY", "k")
    assert llm_generate("Q") == "Salut [2]"
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["key"] == "k" and seen["version"] == "2023-06-01"
    assert seen["body"]["messages"] == [{"role": "user", "content": "Q"}] and seen["body"]["max_tokens"] == 700


def test_retries_then_success(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    _use(monkeypatch, handler)
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_MODEL", "m")
    assert llm_generate("x") == "ok" and calls["n"] == 3


def test_retries_exhausted(monkeypatch):
    _use(monkeypatch, lambda r: httpx.Response(429, text="slow down"))
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("LLM_MAX_RETRIES", "1")
    with pytest.raises(LLMError, match="2 tentative"):
        llm_generate("x")


def test_client_error_not_retried_and_key_not_leaked(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(401, text="invalid key")

    _use(monkeypatch, handler)
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("LLM_API_KEY", "TOPSECRET")
    with pytest.raises(LLMError) as err:
        llm_generate("x")
    assert calls["n"] == 1 and "401" in str(err.value) and "TOPSECRET" not in str(err.value)


def test_network_error_and_bad_format(monkeypatch):
    def boom(request):
        raise httpx.ConnectError("down")

    _use(monkeypatch, boom)
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("LLM_MAX_RETRIES", "0")
    with pytest.raises(LLMError, match="indisponible"):
        llm_generate("x")
    _use(monkeypatch, lambda r: httpx.Response(200, json={"oops": 1}))
    with pytest.raises(LLMError, match="inattendu"):
        llm_generate("x")


def test_invalid_numeric_setting(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("LLM_MAX_TOKENS", "beaucoup")
    with pytest.raises(LLMNotConfiguredError, match="numérique"):
        llm_generate("x")

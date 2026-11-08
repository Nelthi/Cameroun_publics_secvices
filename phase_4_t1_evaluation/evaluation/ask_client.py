"""Client POST /ask — modes http et mock.

Important :
- Une erreur réseau / timeout / HTTP 4xx-5xx lève AskClientError.
- Cela n'est JAMAIS assimilé à un refus correct (refused=true).
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional, Protocol

import httpx

from .config import EvalConfig, load_config
from .exceptions import AskClientError
from .models import AskResponse, QuestionCase, SourceRef


def parse_ask_response(payload: Any, *, fallback_duration_ms: float = 0.0) -> AskResponse:
    """Valide et convertit le JSON de réponse /ask (contrat provisoire)."""
    if not isinstance(payload, dict):
        raise AskClientError("La réponse /ask doit être un objet JSON.")

    required = ("request_id", "answer", "refused", "sources", "duration_ms")
    missing = [field for field in required if field not in payload]
    if missing:
        raise AskClientError(
            "Champs manquants dans la réponse /ask : " + ", ".join(missing)
        )

    request_id = payload["request_id"]
    answer = payload["answer"]
    refused = payload["refused"]
    sources_raw = payload["sources"]
    duration_ms = payload["duration_ms"]

    if not isinstance(request_id, str) or not request_id.strip():
        raise AskClientError("request_id invalide dans la réponse /ask.")
    if not isinstance(answer, str):
        raise AskClientError("answer doit être une chaîne.")
    if not isinstance(refused, bool):
        raise AskClientError("refused doit être un booléen.")
    if not isinstance(sources_raw, list):
        raise AskClientError("sources doit être une liste.")
    if isinstance(duration_ms, bool) or not isinstance(duration_ms, (int, float)):
        raise AskClientError("duration_ms doit être un nombre.")
    if float(duration_ms) < 0:
        raise AskClientError("duration_ms ne peut pas être négatif.")

    sources: list[SourceRef] = []
    for index, item in enumerate(sources_raw):
        if not isinstance(item, dict):
            raise AskClientError(f"sources[{index}] doit être un objet.")
        document_id = item.get("document_id")
        if not isinstance(document_id, str) or not document_id.strip():
            raise AskClientError(f"sources[{index}].document_id invalide.")
        chunk_id = item.get("chunk_id")
        if chunk_id is not None and (
            not isinstance(chunk_id, str) or not chunk_id.strip()
        ):
            raise AskClientError(f"sources[{index}].chunk_id invalide.")
        source_page = item.get("source_page")
        if source_page is not None and (
            not isinstance(source_page, int) or isinstance(source_page, bool)
        ):
            raise AskClientError(f"sources[{index}].source_page invalide.")
        sources.append(
            SourceRef(
                document_id=document_id.strip(),
                chunk_id=chunk_id.strip() if isinstance(chunk_id, str) else None,
                source_page=source_page,
            )
        )

    measured = float(duration_ms) if float(duration_ms) > 0 else float(fallback_duration_ms)
    return AskResponse(
        request_id=request_id.strip(),
        answer=answer,
        refused=refused,
        sources=tuple(sources),
        duration_ms=measured,
    )


class AskClient(Protocol):
    def ask(self, case: QuestionCase) -> AskResponse:
        """Envoie une question et retourne la réponse /ask."""


class HttpAskClient:
    """Client HTTP réel vers POST /ask."""

    def __init__(self, config: EvalConfig, client: Optional[httpx.Client] = None) -> None:
        self._config = config
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=config.http_timeout_seconds)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "HttpAskClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def ask(self, case: QuestionCase) -> AskResponse:
        body = {
            "question": case.question,
            "language": case.language,
        }
        started = time.perf_counter()
        try:
            response = self._client.post(self._config.ask_url, json=body)
        except httpx.TimeoutException as exc:
            raise AskClientError(
                f"Timeout en appelant {self._config.ask_url}"
            ) from exc
        except httpx.HTTPError as exc:
            raise AskClientError(
                f"Erreur réseau vers {self._config.ask_url} : {exc}"
            ) from exc

        elapsed_ms = (time.perf_counter() - started) * 1000.0

        if response.status_code >= 400:
            raise AskClientError(
                f"HTTP {response.status_code} depuis /ask : {response.text[:200]}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise AskClientError("Réponse /ask non JSON.") from exc

        return parse_ask_response(payload, fallback_duration_ms=elapsed_ms)


class MockAskClient:
    """Client fictif déterministe pour développement sans serveur /ask.

    Heuristique simple alignée sur data/questions.json :
    - hors-sujet / vague → refused=true
    - sinon → refused=false + première source attendue du cas si fournie
    """

    _REFUSAL_MARKERS = (
        "recette",
        "football",
        "horoscope",
        "bitcoin",
        "blague",
        "météo",
        "meteo",
        "comment faire ?",
        "comment faire",
    )

    def ask(self, case: QuestionCase) -> AskResponse:
        started = time.perf_counter()
        text = case.question.strip().lower()
        request_id = f"REQ-MOCK-{uuid.uuid4().hex[:8].upper()}"

        should_refuse = case.expected.refused or any(
            marker in text for marker in self._REFUSAL_MARKERS
        )

        if should_refuse:
            response = AskResponse(
                request_id=request_id,
                answer="",
                refused=True,
                sources=(),
                duration_ms=0.0,
            )
        else:
            sources = case.expected.sources
            response = AskResponse(
                request_id=request_id,
                answer="Réponse mock basée sur les sources attendues (fictive).",
                refused=False,
                sources=sources,
                duration_ms=0.0,
            )

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return AskResponse(
            request_id=response.request_id,
            answer=response.answer,
            refused=response.refused,
            sources=response.sources,
            duration_ms=max(elapsed_ms, 0.1),
        )


def create_ask_client(config: Optional[EvalConfig] = None) -> AskClient:
    """Factory : mock ou HTTP selon EVAL_ASK_MODE."""
    cfg = config or load_config()
    if cfg.ask_mode == "mock":
        return MockAskClient()
    return HttpAskClient(cfg)

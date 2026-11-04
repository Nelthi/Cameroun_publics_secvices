import json
import os
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .exceptions import LLMProviderError, RagConfigError


class OpenAICompatibleChatModel:
    """Client minimal pour toute API compatible avec /v1/chat/completions.

    Compatible avec les fournisseurs hébergeant une API OpenAI-compatible et
    avec les serveurs locaux qui exposent cette interface (ex. Ollama).
    """

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: int = 90,
    ):
        if not model or not model.strip():
            raise RagConfigError("Le nom du modèle LLM est obligatoire.")
        if not base_url or not base_url.strip():
            raise RagConfigError("RAG_API_BASE_URL est obligatoire.")
        if not isinstance(timeout, int) or timeout < 1:
            raise RagConfigError("timeout doit être un entier positif.")
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    @classmethod
    def from_env(cls):
        model = os.getenv("RAG_MODEL", "")
        base_url = os.getenv("RAG_API_BASE_URL", "")
        api_key = os.getenv("RAG_API_KEY")
        if not model or not base_url:
            raise RagConfigError(
                "Configurez RAG_MODEL et RAG_API_BASE_URL. "
                "RAG_API_KEY est facultative pour un serveur local."
            )
        return cls(model=model, base_url=base_url, api_key=api_key)

    def generate(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise LLMProviderError("Le fournisseur LLM a renvoyé une réponse vide.")
            return content.strip()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise LLMProviderError(f"Erreur HTTP du fournisseur LLM ({exc.code}) : {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise LLMProviderError(f"Impossible de joindre le fournisseur LLM : {exc}") from exc
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMProviderError("Réponse invalide reçue du fournisseur LLM.") from exc

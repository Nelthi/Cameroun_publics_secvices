"""Classe de base Agent : recherche (Phase 2) -> prompt -> LLM -> brouillon sourcé."""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Callable

from .citations import remap_citations
from .exceptions import ContractError, LLMError, RetrievalError
from .messages import NO_ANSWER, normalize_language
from .privacy import mask_sensitive
from .prompts import build_prompt

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 4
MAX_QUESTION_CHARS = 1000
MAX_PASSAGE_CHARS = 1500


def _fold(text: str) -> str:
    """Minuscules, sans accents ni ponctuation, espaces réduits (comparaison de phrases)."""
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _strip_citations(text: str) -> str:
    return re.sub(r"\[\d+\]", " ", text)


def normalize_passages(raw, max_chars: int = MAX_PASSAGE_CHARS) -> list[dict]:
    """Vérifie le format renvoyé par search() (Phase 2) et le met au propre.

    Passage attendu : {chunk_id, document_id, source_page, text, score, ...}. Les passages au
    texte vide et les chunk_id en double sont ignorés. Tout champ manquant lève RetrievalError.
    """
    if not isinstance(raw, list):
        raise RetrievalError("search() doit renvoyer une liste de passages")
    passages, seen = [], set()
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise RetrievalError(f"passage n°{i} : objet attendu")
        for field in ("chunk_id", "document_id", "source_page", "text"):
            if field not in item:
                raise RetrievalError(f"passage n°{i} sans champ '{field}'")
        text = str(item["text"]).strip()
        if not text or item["chunk_id"] in seen:
            continue
        try:
            page = int(item["source_page"])
            score = float(item.get("score", 0.0))
        except (TypeError, ValueError) as exc:
            raise RetrievalError(f"passage n°{i} : source_page ou score non numérique") from exc
        seen.add(item["chunk_id"])
        passages.append({
            "rank": len(passages) + 1,
            "score": round(min(max(score, 0.0), 1.0), 4),
            "chunk_id": str(item["chunk_id"]),
            "document_id": str(item["document_id"]),
            "source_page": page,
            "text": text[:max_chars],
        })
    return passages


class Agent:
    """Agent spécialisé. Les sous-classes fixent `name`, `role` et `instruction`.

    search_fn(query, top_k) -> passages (format Phase 2) ; llm_fn(prompt) -> texte.
    Si absents, on utilise backend.rag.search et llm_generate (import différé : un test
    avec de faux search/LLM n'a besoin ni de FAISS ni de modèle).
    """

    name = "base"
    role = "Agent"
    instruction = ""
    query_hint = ""  # mots ajoutés à la question pour orienter la recherche

    def __init__(self, search_fn: Callable | None = None, llm_fn: Callable[[str], str] | None = None,
                 top_k: int = DEFAULT_TOP_K):
        if top_k < 1:
            raise ValueError("top_k doit être >= 1")
        self._search_fn = search_fn
        self._llm_fn = llm_fn
        self.top_k = top_k

    # -- dépendances ---------------------------------------------------------
    def _search(self, query: str, top_k: int):
        if self._search_fn is not None:
            return self._search_fn(query, top_k)
        from backend.rag import search  # import différé
        return search(query, top_k=top_k)

    def _llm(self, prompt: str) -> str:
        if self._llm_fn is not None:
            return self._llm_fn(prompt)
        from .llm import llm_generate
        return llm_generate(prompt)

    # -- étapes --------------------------------------------------------------
    def build_query(self, question: str, plan: dict) -> str:
        return f"{question} {self.query_hint}".strip() if self.query_hint else question

    def retrieve(self, query: str) -> list[dict]:
        try:
            raw = self._search(query, self.top_k)
        except RetrievalError:
            raise
        except Exception as exc:  # index absent, modèle introuvable, question vide...
            raise RetrievalError(f"recherche impossible : {exc}") from exc
        return normalize_passages(raw)

    def run(self, question: str, plan: dict, language: str = "fr") -> dict:
        """Produit le brouillon (contrat T2) pour la question et le plan de routage T1."""
        language = normalize_language(language)
        request_id = plan["request_id"]
        clean_question, meta = prepare_question(question)
        meta.update({"kind": "rag", "language": language, "no_answer": False})

        passages = self.retrieve(self.build_query(clean_question, plan))
        if not passages:
            meta.update({"no_answer": True, "reason": "no_passages"})
            return make_draft(request_id, self.name, NO_ANSWER[language], [], [], meta)

        prompt = build_prompt(role=self.role, instruction=self.instruction, passages=passages,
                              question=clean_question, language=language)
        try:
            raw_answer = self._llm(prompt)
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"échec du LLM : {exc}") from exc
        if not isinstance(raw_answer, str) or not raw_answer.strip():
            raise LLMError("le LLM a renvoyé une réponse vide")

        answer, used, invalid = remap_citations(raw_answer, len(passages))
        if invalid:
            meta["invalid_citations_removed"] = invalid
            logger.warning("%s : renvois invalides supprimés %s", self.name, invalid)

        sentence = NO_ANSWER[language]
        folded_answer = _fold(_strip_citations(answer))
        if _fold(sentence) in folded_answer:
            remainder = folded_answer.replace(_fold(sentence), "").strip()
            if len(remainder) < 25:  # le LLM ne dit que « je ne sais pas »
                meta["no_answer"] = True
                return make_draft(request_id, self.name, sentence, [], passages, meta)
            meta["admits_missing_info"] = True  # réponse partielle

        if not answer:
            raise LLMError("réponse vide après nettoyage des renvois")
        citations = [
            {"chunk_id": passages[i - 1]["chunk_id"], "document_id": passages[i - 1]["document_id"],
             "source_page": passages[i - 1]["source_page"]}
            for i in used
        ]
        return make_draft(request_id, self.name, answer, citations, passages, meta)


def prepare_question(question) -> tuple[str, dict]:
    """Nettoie, masque les données personnelles et tronque. Retourne (question, meta)."""
    if not isinstance(question, str) or not question.strip():
        raise ContractError("la question est vide ou n'est pas un texte")
    text = re.sub(r"\s+", " ", question).strip()
    meta: dict = {}
    if len(text) > MAX_QUESTION_CHARS:
        text, meta["question_truncated"] = text[:MAX_QUESTION_CHARS].rstrip(), True
    text, masked = mask_sensitive(text)
    if masked:
        meta["sensitive_data_masked"] = True
    return text, meta


def make_draft(request_id: str, agent: str, answer: str, citations: list[dict],
               passages: list[dict], meta: dict) -> dict:
    """Assemble le brouillon au format du contrat T2."""
    top_score = max((p["score"] for p in passages), default=0.0)
    return {
        "request_id": request_id,
        "agent": agent,
        "answer_draft": answer,
        "citations": citations,
        "retrieval": {"top_score": top_score, "n_chunks": len(passages), "passages": passages},
        "meta": meta,
    }

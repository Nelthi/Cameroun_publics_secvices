from typing import Any, Dict, List, Optional

from ..vector_store.store import FaissVectorStore
from .exceptions import EmptyQueryError, RetrievalConfigError
from .models import RetrievedChunk, RetrievalResponse


class RetrievalEngine:
    """Sélectionne les chunks pertinents à partir de l'index FAISS.

    Le moteur délègue la vectorisation de la question et la recherche exacte à
    FaissVectorStore, puis applique les filtres métier et prépare le contexte
    sourcé destiné à l'étape RAG/aux agents.
    """

    def __init__(
        self,
        vector_store: Optional[FaissVectorStore] = None,
        data_root: str = "data",
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        min_score: Optional[float] = None,
        candidate_k: int = 50,
        context_char_limit: int = 12000,
        include_inactive: bool = False,
    ):
        if min_score is not None and not isinstance(min_score, (int, float)):
            raise RetrievalConfigError("min_score doit être un nombre ou None.")
        if min_score is not None and not -1.0 <= float(min_score) <= 1.0:
            raise RetrievalConfigError("min_score doit être compris entre -1 et 1.")
        if not isinstance(candidate_k, int) or candidate_k < 1:
            raise RetrievalConfigError("candidate_k doit être un entier >= 1.")
        if not isinstance(context_char_limit, int) or context_char_limit < 1:
            raise RetrievalConfigError("context_char_limit doit être un entier >= 1.")

        if vector_store is None:
            kwargs: Dict[str, Any] = {"data_root": data_root, "device": device}
            if model_name:
                kwargs["model_name"] = model_name
            vector_store = FaissVectorStore(**kwargs)
        self.vector_store = vector_store
        self.min_score = float(min_score) if min_score is not None else None
        self.candidate_k = candidate_k
        self.context_char_limit = context_char_limit
        self.include_inactive = include_inactive

    @staticmethod
    def _matches_filter(value: Any, expected: Optional[str]) -> bool:
        if expected is None:
            return True
        return str(value or "").strip().casefold() == expected.strip().casefold()

    def _build_context(self, results: List[RetrievedChunk]) -> str:
        sections: List[str] = []
        used = 0
        for item in results:
            title = item.metadata.get("title") or "Document sans titre"
            institution = item.metadata.get("institution") or "Institution non précisée"
            page = f", page {item.page_number}" if item.page_number is not None else ""
            source_url = item.metadata.get("source_url")
            reliability = item.metadata.get("reliability")
            verification_date = item.metadata.get("verification_date")
            source_details = []
            if source_url:
                source_details.append(f"URL {source_url}")
            if reliability:
                source_details.append(f"fiabilité {reliability}")
            if verification_date:
                source_details.append(f"vérifié le {verification_date}")
            details = " | " + " | ".join(source_details) if source_details else ""
            section = (
                f"[Source: {title} | {institution} | document {item.document_id}"
                f" | chunk {item.chunk_id}{page}{details} | score {item.score:.4f}]\n"
                f"{item.text.strip()}"
            )
            remaining = self.context_char_limit - used
            if remaining <= 0:
                break
            if len(section) > remaining:
                section = section[:remaining].rstrip()
            sections.append(section)
            used += len(section) + 2
            if used >= self.context_char_limit:
                break
        return "\n\n".join(sections)

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        domain: Optional[str] = None,
        subdomain: Optional[str] = None,
        min_score: Optional[float] = None,
    ) -> RetrievalResponse:
        if not isinstance(query, str) or not query.strip():
            raise EmptyQueryError("La question ne peut pas être vide.")
        if not isinstance(top_k, int) or top_k < 1:
            raise RetrievalConfigError("top_k doit être un entier >= 1.")
        threshold = self.min_score if min_score is None else min_score
        if threshold is not None and (not isinstance(threshold, (int, float)) or not -1 <= threshold <= 1):
            raise RetrievalConfigError("min_score doit être compris entre -1 et 1.")

        # La recherche de candidats est plus large que top_k afin de conserver
        # suffisamment de résultats après application des filtres de domaine.
        candidates = self.vector_store.search(query.strip(), top_k=self.candidate_k)
        selected: List[RetrievedChunk] = []
        for item in candidates:
            metadata = item.metadata or {}
            if not self._matches_filter(metadata.get("domain"), domain):
                continue
            if not self._matches_filter(metadata.get("subdomain"), subdomain):
                continue
            if not self.include_inactive and str(metadata.get("status", "active")).casefold() != "active":
                continue
            if threshold is not None and item.score < float(threshold):
                continue
            selected.append(RetrievedChunk(
                rank=len(selected) + 1,
                score=float(item.score),
                document_id=item.document_id,
                chunk_id=item.chunk_id,
                text=item.text,
                page_number=item.page_number,
                metadata=metadata,
            ))
            if len(selected) >= top_k:
                break

        return RetrievalResponse(
            query=query.strip(),
            results=selected,
            context=self._build_context(selected),
        )

from typing import Any, Dict, List, Optional

from ..retrieval.engine import RetrievalEngine
from ..retrieval.models import RetrievedChunk
from .exceptions import RagConfigError
from .models import RagResponse, SourceReference
from .prompt_builder import build_messages


NO_EVIDENCE_ANSWER = (
    "Je ne trouve pas, dans les documents actuellement disponibles, "
    "d'informations suffisantes pour répondre de manière fiable à cette question. "
    "Veuillez vérifier auprès de l'administration compétente."
)


class RagPipeline:
    """Relie la récupération documentaire à un modèle de génération."""

    def __init__(
        self,
        retriever: Optional[RetrievalEngine] = None,
        llm: Any = None,
        top_k: int = 5,
        domain: Optional[str] = None,
        subdomain: Optional[str] = None,
        min_score: Optional[float] = None,
        temperature: float = 0.1,
    ):
        if not isinstance(top_k, int) or top_k < 1:
            raise RagConfigError("top_k doit être un entier >= 1.")
        if not 0 <= temperature <= 2:
            raise RagConfigError("temperature doit être comprise entre 0 et 2.")
        self.retriever = retriever or RetrievalEngine()
        self.llm = llm
        self.top_k = top_k
        self.domain = domain
        self.subdomain = subdomain
        self.min_score = min_score
        self.temperature = temperature

    @staticmethod
    def _sources(chunks: List[RetrievedChunk]) -> List[SourceReference]:
        sources = []
        seen = set()
        for index, chunk in enumerate(chunks, start=1):
            key = (chunk.document_id, chunk.chunk_id)
            if key in seen:
                continue
            seen.add(key)
            metadata: Dict[str, Any] = chunk.metadata or {}
            sources.append(SourceReference(
                label=f"S{index}",
                document_id=chunk.document_id,
                chunk_id=chunk.chunk_id,
                title=str(metadata.get("title") or "Document sans titre"),
                institution=str(metadata.get("institution") or "Institution non précisée"),
                page_number=chunk.page_number,
                source_url=metadata.get("source_url"),
                score=float(chunk.score),
            ))
        return sources

    def ask(self, question: str) -> RagResponse:
        if not isinstance(question, str) or not question.strip():
            raise RagConfigError("La question ne peut pas être vide.")
        retrieval = self.retriever.retrieve(
            question,
            top_k=self.top_k,
            domain=self.domain,
            subdomain=self.subdomain,
            min_score=self.min_score,
        )
        if not retrieval.results:
            return RagResponse(
                question=question.strip(), answer=NO_EVIDENCE_ANSWER,
                abstained=True,
                reason="Aucun passage documentaire pertinent n'a été retrouvé.",
                sources=[], retrieved_count=0,
                model=getattr(self.llm, "model", None),
            )
        if self.llm is None:
            raise RagConfigError("Aucun modèle LLM n'est configuré pour générer la réponse.")

        messages = build_messages(question, retrieval.results)
        answer = self.llm.generate(messages, temperature=self.temperature)
        if not isinstance(answer, str) or not answer.strip():
            raise RagConfigError("Le modèle LLM a renvoyé une réponse vide.")
        return RagResponse(
            question=question.strip(),
            answer=answer.strip(),
            abstained=False,
            reason=None,
            sources=self._sources(retrieval.results),
            retrieved_count=len(retrieval.results),
            model=getattr(self.llm, "model", None),
        )

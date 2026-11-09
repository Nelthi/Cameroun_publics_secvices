"""Contrats JSON de la Phase 3 (modèles Pydantic).

Chaque modèle est volontairement tolérant : un champ EN PLUS est accepté,
un champ OBLIGATOIRE manquant ou d'un mauvais type est refusé avec un message
qui nomme le champ. Ainsi, si une tâche s'écarte du contrat, on sait laquelle.
"""
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict


class Contract(BaseModel):
    model_config = ConfigDict(extra="allow")


class Citation(Contract):
    chunk_id: str
    document_id: str
    source_page: int


class Retrieval(Contract):
    top_score: float = 0.0
    n_chunks: int = 0


class Gap(Contract):
    topic: str
    reason: str = "unknown"


# ---- T1 -> T4 : plan de routage
class RoutingOut(Contract):
    request_id: str
    intent: str
    domain: Optional[str] = None
    subdomain: Optional[str] = None
    agents: List[str]
    needs_clarification: bool = False


# ---- T2 -> T4 : brouillon de l'agent
class AgentOut(Contract):
    request_id: str
    agent: Optional[str] = None
    answer_draft: str
    citations: List[Citation] = []
    retrieval: Retrieval = Retrieval()


# ---- T3 -> T4 : réponse validée
class ValidationOut(Contract):
    request_id: str
    status: Literal["approved", "partial", "refused"]
    final_answer: str
    citations: List[Citation] = []
    checks: Dict[str, bool] = {}
    gaps: List[Gap] = []


# ---- T4 -> client : réponse de l'API
class Source(BaseModel):
    document_id: str
    source_page: int


class AskOut(BaseModel):
    request_id: str
    status: str  # approved | partial | refused | needs_clarification | error
    answer: str
    sources: List[Source]
    timestamp: str

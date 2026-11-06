import pytest

from backend.knowledge_base.retrieval.engine import RetrievalEngine
from backend.knowledge_base.retrieval.exceptions import (
    EmptyQueryError,
    RetrievalConfigError,
)
from backend.knowledge_base.vector_store.models import VectorSearchResult


class FakeVectorStore:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def search(self, query, top_k=5):
        self.calls.append((query, top_k))
        return self.items[:top_k]


def result(rank, score, domain="public_services", subdomain="national_identity_card",
           status="active", text=None, document_id=None):
    doc_id = document_id or f"DOC-{rank:012X}"
    chunk_id = f"CHK-{rank:012X}-0001"
    return VectorSearchResult(
        rank=rank,
        score=score,
        document_id=doc_id,
        chunk_id=chunk_id,
        text=text or f"Contenu pertinent numéro {rank}.",
        page_number=rank,
        metadata={
            "domain": domain,
            "subdomain": subdomain,
            "status": status,
            "title": f"Document {rank}",
            "institution": "DGSN",
        },
    )


def test_retrieve_returns_top_k_and_context():
    store = FakeVectorStore([result(1, .91), result(2, .82), result(3, .70)])
    response = RetrievalEngine(vector_store=store).retrieve("Documents CNI", top_k=2)
    assert len(response.results) == 2
    assert response.results[0].score == .91
    assert "Document 1" in response.context
    assert "page 1" in response.context


def test_domain_and_subdomain_filters_are_applied():
    store = FakeVectorStore([
        result(1, .95, domain="taxes", subdomain="income_tax"),
        result(2, .90, domain="public_services", subdomain="national_identity_card"),
    ])
    response = RetrievalEngine(vector_store=store).retrieve(
        "CNI", domain="PUBLIC_SERVICES", subdomain="national_identity_card"
    )
    assert [item.document_id for item in response.results] == ["DOC-000000000002"]


def test_inactive_documents_are_excluded_by_default():
    store = FakeVectorStore([result(1, .99, status="inactive"), result(2, .80)])
    response = RetrievalEngine(vector_store=store).retrieve("question")
    assert [item.document_id for item in response.results] == ["DOC-000000000002"]


def test_inactive_documents_can_be_included():
    store = FakeVectorStore([result(1, .99, status="inactive")])
    response = RetrievalEngine(vector_store=store, include_inactive=True).retrieve("question")
    assert len(response.results) == 1


def test_min_score_filters_low_scores():
    store = FakeVectorStore([result(1, .90), result(2, .40)])
    response = RetrievalEngine(vector_store=store, min_score=.60).retrieve("question")
    assert len(response.results) == 1


def test_candidate_search_is_broader_than_requested_top_k():
    store = FakeVectorStore([result(1, .9)])
    RetrievalEngine(vector_store=store, candidate_k=37).retrieve("question", top_k=2)
    assert store.calls == [("question", 37)]


def test_empty_query_is_rejected():
    with pytest.raises(EmptyQueryError):
        RetrievalEngine(vector_store=FakeVectorStore([])).retrieve("   ")


@pytest.mark.parametrize("kwargs", [
    {"candidate_k": 0},
    {"context_char_limit": 0},
    {"min_score": 1.5},
])
def test_invalid_engine_configuration_is_rejected(kwargs):
    with pytest.raises(RetrievalConfigError):
        RetrievalEngine(vector_store=FakeVectorStore([]), **kwargs)


def test_invalid_top_k_is_rejected():
    with pytest.raises(RetrievalConfigError):
        RetrievalEngine(vector_store=FakeVectorStore([])).retrieve("question", top_k=0)


def test_context_respects_character_limit():
    store = FakeVectorStore([result(1, .9, text="x" * 200)])
    response = RetrievalEngine(vector_store=store, context_char_limit=50).retrieve("question")
    assert len(response.context) <= 50


def test_no_match_returns_empty_results_and_context():
    store = FakeVectorStore([result(1, .9, domain="taxes")])
    response = RetrievalEngine(vector_store=store).retrieve("CNI", domain="public_services")
    assert response.results == []
    assert response.context == ""


def test_to_dict_is_serializable_shape():
    response = RetrievalEngine(vector_store=FakeVectorStore([result(1, .9)])).retrieve("question")
    payload = response.to_dict()
    assert payload["query"] == "question"
    assert payload["result_count"] == 1
    assert payload["results"][0]["chunk_id"].startswith("CHK-")

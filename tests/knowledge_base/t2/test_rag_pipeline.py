import pytest

from backend.knowledge_base.rag.exceptions import RagConfigError
from backend.knowledge_base.rag.pipeline import NO_EVIDENCE_ANSWER, RagPipeline
from backend.knowledge_base.retrieval.models import RetrievedChunk, RetrievalResponse


class FakeRetriever:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def retrieve(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return RetrievalResponse(query=query, results=self.results, context="")


class FakeLLM:
    model = "fake-model"

    def __init__(self, answer="Réponse fondée sur [S1]."):
        self.answer = answer
        self.calls = []

    def generate(self, messages, temperature=0.1):
        self.calls.append((messages, temperature))
        return self.answer


def sample_chunk():
    return RetrievedChunk(
        rank=1, score=0.91, document_id="DOC-123", chunk_id="CHUNK-1",
        text="Extrait documentaire de test.", page_number=4,
        metadata={"title": "Guide CNI", "institution": "DGSN", "source_url": "https://example.org", "domain": "public_services"},
    )


def test_pipeline_retrieves_and_generates_answer_with_source():
    retriever, llm = FakeRetriever([sample_chunk()]), FakeLLM()
    response = RagPipeline(retriever=retriever, llm=llm, domain="public_services").ask("Question CNI")
    assert response.answer == "Réponse fondée sur [S1]."
    assert response.abstained is False
    assert response.sources[0].label == "S1"
    assert response.sources[0].page_number == 4
    assert retriever.calls[0][1]["domain"] == "public_services"
    assert "Extrait documentaire de test" in llm.calls[0][0][1]["content"]


def test_pipeline_abstains_when_no_evidence_and_does_not_call_llm():
    llm = FakeLLM()
    response = RagPipeline(retriever=FakeRetriever([]), llm=llm).ask("Question inconnue")
    assert response.abstained is True
    assert response.answer == NO_EVIDENCE_ANSWER
    assert llm.calls == []
    assert response.sources == []


def test_pipeline_requires_llm_only_when_evidence_exists():
    with pytest.raises(RagConfigError):
        RagPipeline(retriever=FakeRetriever([sample_chunk()])).ask("Question")


def test_empty_question_is_rejected():
    with pytest.raises(RagConfigError):
        RagPipeline(retriever=FakeRetriever([]), llm=FakeLLM()).ask(" ")


@pytest.mark.parametrize("kwargs", [{"top_k": 0}, {"temperature": 2.1}, {"temperature": -0.1}])
def test_invalid_configuration_is_rejected(kwargs):
    with pytest.raises(RagConfigError):
        RagPipeline(retriever=FakeRetriever([]), llm=FakeLLM(), **kwargs)


def test_source_deduplication():
    chunk = sample_chunk()
    response = RagPipeline(retriever=FakeRetriever([chunk, chunk]), llm=FakeLLM()).ask("Question")
    assert len(response.sources) == 1

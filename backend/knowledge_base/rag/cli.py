import argparse
import json

from ..embeddings.generator import DEFAULT_MODEL
from ..retrieval.engine import RetrievalEngine
from .pipeline import RagPipeline
from .providers import OpenAICompatibleChatModel


def main():
    parser = argparse.ArgumentParser(description="Pose une question à la Knowledge Base via un pipeline RAG.")
    parser.add_argument("question", help="Question du citoyen")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--domain", help="Ex. public_services")
    parser.add_argument("--subdomain", help="Ex. national_identity_card")
    parser.add_argument("--min-score", type=float)
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--embedding-model", default=DEFAULT_MODEL)
    parser.add_argument("--device", choices=["cpu", "cuda", "mps"])
    parser.add_argument("--temperature", type=float, default=0.1)
    args = parser.parse_args()

    llm = OpenAICompatibleChatModel.from_env()
    retriever = RetrievalEngine(
        data_root=args.data_root,
        model_name=args.embedding_model,
        device=args.device,
    )
    pipeline = RagPipeline(
        retriever=retriever,
        llm=llm,
        top_k=args.top_k,
        domain=args.domain,
        subdomain=args.subdomain,
        min_score=args.min_score,
        temperature=args.temperature,
    )
    print(json.dumps(pipeline.ask(args.question).to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

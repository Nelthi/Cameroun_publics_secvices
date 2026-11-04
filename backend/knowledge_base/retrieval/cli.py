import argparse
import json

from ..embeddings.generator import DEFAULT_MODEL
from .engine import RetrievalEngine


def main():
    parser = argparse.ArgumentParser(description="Recherche des passages pertinents dans la Knowledge Base.")
    parser.add_argument("question", help="Question à poser à la base documentaire")
    parser.add_argument("--top-k", type=int, default=5, help="Nombre maximal de passages retournés")
    parser.add_argument("--candidate-k", type=int, default=50, help="Nombre de candidats examinés dans FAISS")
    parser.add_argument("--domain", help="Filtrer par domaine, ex. public_services")
    parser.add_argument("--subdomain", help="Filtrer par sous-domaine, ex. national_identity_card")
    parser.add_argument("--min-score", type=float, help="Seuil minimal de similarité cosinus (-1 à 1)")
    parser.add_argument("--context-char-limit", type=int, default=12000, help="Taille maximale du contexte préparé")
    parser.add_argument("--data-root", default="data", help="Dossier de données")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Modèle Sentence Transformers")
    parser.add_argument("--device", choices=["cpu", "cuda", "mps"], help="Périphérique de calcul")
    parser.add_argument("--include-inactive", action="store_true", help="Inclure les documents inactifs")
    args = parser.parse_args()

    engine = RetrievalEngine(
        data_root=args.data_root,
        model_name=args.model,
        device=args.device,
        candidate_k=args.candidate_k,
        min_score=args.min_score,
        context_char_limit=args.context_char_limit,
        include_inactive=args.include_inactive,
    )
    response = engine.retrieve(
        args.question,
        top_k=args.top_k,
        domain=args.domain,
        subdomain=args.subdomain,
    )
    print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

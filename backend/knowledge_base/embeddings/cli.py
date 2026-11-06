import argparse
import json

from .generator import DEFAULT_MODEL, EmbeddingGenerator


def main():
    parser = argparse.ArgumentParser(
        description="Transforme les chunks en embeddings pour la recherche sémantique."
    )
    parser.add_argument("document_id", nargs="?", help="Identifiant DOC-... à vectoriser")
    parser.add_argument("--all", action="store_true", help="Vectoriser tous les documents chunkés")
    parser.add_argument("--domain", help="Limiter le traitement à un domaine")
    parser.add_argument("--data-root", default="data", help="Dossier data/ (défaut : data)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Identifiant du modèle Sentence Transformers")
    parser.add_argument("--batch-size", type=int, default=32, help="Nombre de chunks traités par lot")
    parser.add_argument("--device", choices=["cpu", "cuda", "mps"], help="Périphérique de calcul (défaut : automatique)")
    args = parser.parse_args()

    if not args.all and not args.document_id:
        parser.error("Indiquez un document_id ou utilisez --all.")
    if args.all and args.document_id:
        parser.error("Utilisez soit document_id, soit --all.")

    generator = EmbeddingGenerator(
        data_root=args.data_root,
        model_name=args.model,
        batch_size=args.batch_size,
        device=args.device,
    )
    if args.all:
        results = [item.to_dict() for item in generator.embed_all(domain=args.domain)]
    else:
        results = [generator.embed_document(args.document_id).to_dict()]
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

import argparse
import json

from .chunker import TextChunker


def main():
    parser = argparse.ArgumentParser(
        description="Découpe les documents traités en chunks pour le pipeline RAG."
    )
    parser.add_argument("document_id", nargs="?", help="Identifiant DOC-... à découper")
    parser.add_argument("--all", action="store_true", help="Découper tous les documents traités")
    parser.add_argument("--domain", help="Limiter le traitement à un domaine")
    parser.add_argument("--data-root", default="data", help="Dossier data/ (défaut : data)")
    parser.add_argument("--chunk-size", type=int, default=1000, help="Taille cible en caractères (défaut : 1000)")
    parser.add_argument("--overlap", type=int, default=150, help="Chevauchement en caractères (défaut : 150)")
    args = parser.parse_args()

    if not args.all and not args.document_id:
        parser.error("Indiquez un document_id ou utilisez --all.")
    if args.all and args.document_id:
        parser.error("Utilisez soit document_id, soit --all.")

    chunker = TextChunker(
        data_root=args.data_root,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )
    if args.all:
        results = [item.to_dict() for item in chunker.chunk_all(domain=args.domain)]
    else:
        results = [chunker.chunk_document(args.document_id).to_dict()]
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

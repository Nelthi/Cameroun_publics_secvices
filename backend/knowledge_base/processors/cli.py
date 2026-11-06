import argparse
import json

from .processor import DocumentProcessor


def main():
    parser = argparse.ArgumentParser(
        description="Extrait et nettoie le texte des documents de la Knowledge Base."
    )
    parser.add_argument("document_id", nargs="?", help="Identifiant DOC-... à traiter")
    parser.add_argument("--all", action="store_true", help="Traiter tous les documents")
    parser.add_argument("--domain", help="Limiter le traitement à un domaine")
    parser.add_argument("--data-root", default="data", help="Dossier data/ (défaut : data)")
    args = parser.parse_args()

    if not args.all and not args.document_id:
        parser.error("Indiquez un document_id ou utilisez --all.")
    if args.all and args.document_id:
        parser.error("Utilisez soit document_id, soit --all.")

    processor = DocumentProcessor(data_root=args.data_root)
    if args.all:
        results = [result.to_dict() for result in processor.process_all(domain=args.domain)]
    else:
        results = [processor.process_document(args.document_id).to_dict()]
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

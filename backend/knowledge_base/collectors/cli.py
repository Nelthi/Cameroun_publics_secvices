import argparse
import json
from pathlib import Path

from .collector import DocumentCollector
from .models import DocumentMetadata


def main():
    parser = argparse.ArgumentParser(
        description="Importer un document dans la Knowledge Base."
    )
    parser.add_argument("file", help="Chemin du fichier PDF, DOCX ou TXT")
    parser.add_argument("--title", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--subdomain", required=True)
    parser.add_argument("--institution", required=True)
    parser.add_argument("--document-type", required=True)
    parser.add_argument("--publication-date")
    parser.add_argument("--source-url")
    parser.add_argument("--reliability", default="unverified")
    parser.add_argument("--verification-date")
    parser.add_argument("--status", default="active")
    parser.add_argument("--language", default="fr")
    parser.add_argument("--data-root", default="data")
    args = parser.parse_args()

    metadata = DocumentMetadata(
        title=args.title,
        domain=args.domain,
        subdomain=args.subdomain,
        institution=args.institution,
        document_type=args.document_type,
        publication_date=args.publication_date,
        source_url=args.source_url,
        reliability=args.reliability,
        verification_date=args.verification_date,
        status=args.status,
        language=args.language,
    )
    collector = DocumentCollector(data_root=args.data_root)
    result = collector.import_document(args.file, metadata)
    print(json.dumps({
        "document_id": result.document_id,
        "original_filename": result.original_filename,
        "stored_path": result.stored_path,
        "file_format": result.file_format,
        "file_size": result.file_size,
        "sha256": result.sha256,
        "imported_at": result.imported_at,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

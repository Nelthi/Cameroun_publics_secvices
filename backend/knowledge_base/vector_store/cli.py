import argparse
import json

from .store import FaissVectorStore
from ..embeddings.generator import DEFAULT_MODEL


def main():
    parser = argparse.ArgumentParser(description="Construit et interroge le Vector Store FAISS.")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--build", action="store_true", help="Construire/reconstruire l'index FAISS")
    actions.add_argument("--search", metavar="QUESTION", help="Rechercher les chunks les plus proches")
    parser.add_argument("--top-k", type=int, default=5, help="Nombre de résultats (défaut : 5)")
    parser.add_argument("--data-root", default="data", help="Dossier de données")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Modèle Sentence Transformers")
    parser.add_argument("--device", choices=["cpu", "cuda", "mps"], help="Périphérique de calcul")
    args = parser.parse_args()

    store = FaissVectorStore(data_root=args.data_root, model_name=args.model, device=args.device)
    if args.build:
        result = store.build_index()
    else:
        result = [item.to_dict() for item in store.search(args.search, top_k=args.top_k)]
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

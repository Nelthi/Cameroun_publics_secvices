"""Construction, sauvegarde, chargement et interrogation de l'index FAISS."""
import json
from pathlib import Path

import faiss
import numpy as np

from .config import DEFAULT_TOP_K, INDEX_PATH, MAPPING_PATH


def build_index(chunks, embedder):
    """Vectorise les fragments et renvoie (index FAISS, mapping).

    mapping = {"0": {...fragment...}, "1": {...}} : la clé est la POSITION
    du vecteur dans l'index. C'est ce qui permet de retrouver le texte.
    """
    if not chunks:
        raise ValueError("Aucun fragment à indexer")
    vectors = np.asarray(embedder.encode([c["text"] for c in chunks]), dtype="float32")
    if vectors.ndim != 2 or vectors.shape[0] != len(chunks):
        raise ValueError(f"Forme de vecteurs inattendue : {vectors.shape}")

    index = faiss.IndexFlatL2(vectors.shape[1])  # recherche exacte, distance L2
    index.add(vectors)
    mapping = {str(i): chunk for i, chunk in enumerate(chunks)}
    return index, mapping


def save_index(index, mapping, index_path=INDEX_PATH, mapping_path=MAPPING_PATH):
    index_path, mapping_path = Path(index_path), Path(mapping_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_path))
    mapping_path.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_index(index_path=INDEX_PATH, mapping_path=MAPPING_PATH):
    index_path, mapping_path = Path(index_path), Path(mapping_path)
    for path in (index_path, mapping_path):
        if not path.exists():
            raise FileNotFoundError(
                f"{path} introuvable. Lancez d'abord : python -m backend.rag.build_index"
            )
    index = faiss.read_index(str(index_path))
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    if index.ntotal != len(mapping):
        raise ValueError(
            f"Index ({index.ntotal} vecteurs) et mapping ({len(mapping)}) "
            "ne correspondent pas : reconstruisez l'index."
        )
    return index, mapping


class VectorStore:
    """Associe un index, son mapping et un embedder pour faire des recherches."""

    def __init__(self, index, mapping, embedder):
        self.index, self.mapping, self.embedder = index, mapping, embedder

    @classmethod
    def from_disk(cls, embedder=None, index_path=INDEX_PATH, mapping_path=MAPPING_PATH):
        if embedder is None:
            from .embedder import Embedder
            embedder = Embedder()
        index, mapping = load_index(index_path, mapping_path)
        return cls(index, mapping, embedder)

    def search(self, query, top_k=DEFAULT_TOP_K):
        """Renvoie les top_k fragments les plus proches de la question.

        Chaque résultat : rank, score (0 à 1, plus haut = plus pertinent),
        distance (L2 au carré, plus bas = plus proche), chunk_id,
        document_id, text, source_page.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("La question ne peut pas être vide")
        if top_k < 1:
            raise ValueError("top_k doit être >= 1")

        k = min(top_k, self.index.ntotal)
        q_vec = np.asarray(self.embedder.encode([query.strip()]), dtype="float32")
        distances, ids = self.index.search(q_vec, k)

        results = []
        for rank, (dist, idx) in enumerate(zip(distances[0], ids[0]), start=1):
            if idx < 0:  # FAISS renvoie -1 quand il n'a pas assez de résultats
                continue
            chunk = self.mapping[str(int(idx))]
            results.append({
                "rank": rank,
                # vecteurs normalisés : d = 2 - 2*cosinus  =>  cosinus = 1 - d/2
                "score": round(float(max(0.0, 1.0 - dist / 2.0)), 4),
                "distance": round(float(dist), 4),
                "chunk_id": chunk["chunk_id"],
                "document_id": chunk["document_id"],
                "text": chunk["text"],
                "source_page": chunk["source_page"],
            })
        return results

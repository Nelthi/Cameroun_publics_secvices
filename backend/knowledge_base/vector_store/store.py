import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .exceptions import (
    EmbeddingFilesError,
    FaissDependencyError,
    VectorIndexNotFoundError,
    VectorSearchError,
    VectorStoreConfigError,
)
from .models import VectorSearchResult
from ..embeddings.generator import DEFAULT_MODEL


class FaissVectorStore:
    """Construit et interroge un index FAISS à partir des embeddings sauvegardés.

    L'index est un IndexFlatIP. Comme les vecteurs du générateur sont normalisés
    en L2, le produit scalaire correspond à la similarité cosinus.
    """

    def __init__(
        self,
        data_root: str | Path = "data",
        model_name: str = DEFAULT_MODEL,
        device: Optional[str] = None,
        encoder: Any = None,
    ):
        if not isinstance(model_name, str) or not model_name.strip():
            raise VectorStoreConfigError("model_name ne peut pas être vide.")
        self.data_root = Path(data_root).resolve()
        self.embeddings_root = self.data_root / "embeddings"
        self.store_root = self.data_root / "vector_store"
        self.store_root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.store_root / "index.faiss"
        self.manifest_path = self.store_root / "metadata.json"
        self.model_name = model_name.strip()
        self.device = device
        self.encoder = encoder

    @staticmethod
    def _faiss():
        try:
            import faiss
            return faiss
        except ImportError as exc:
            raise FaissDependencyError(
                "FAISS n'est pas installé. Exécutez : python -m pip install faiss-cpu"
            ) from exc

    @staticmethod
    def _load_json(path: Path) -> Dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EmbeddingFilesError(f"Fichier JSON illisible ({path}) : {exc}") from exc
        if not isinstance(payload, dict):
            raise EmbeddingFilesError(f"Format JSON invalide : {path}")
        return payload

    def _collect_embeddings(self):
        if not self.embeddings_root.exists():
            raise EmbeddingFilesError("Aucun dossier data/embeddings. Générez d'abord les embeddings.")

        matrices: List[np.ndarray] = []
        records: List[Dict[str, Any]] = []
        dimension = None
        found_files = sorted(self.embeddings_root.rglob("metadata.json"))

        for manifest_path in found_files:
            manifest = self._load_json(manifest_path)
            embedding_info = manifest.get("embedding", {})
            if embedding_info.get("status") != "embedded":
                continue
            if embedding_info.get("model_name") != self.model_name:
                raise EmbeddingFilesError(
                    "Tous les documents d'un même index doivent utiliser le même modèle. "
                    f"Modèle trouvé : {embedding_info.get('model_name')!r}, attendu : {self.model_name!r}."
                )

            vectors_path = manifest_path.parent / "vectors.npy"
            try:
                matrix = np.load(vectors_path, allow_pickle=False)
            except (OSError, ValueError) as exc:
                raise EmbeddingFilesError(f"Impossible de charger {vectors_path} : {exc}") from exc

            if matrix.ndim != 2 or matrix.shape[0] != len(manifest.get("items", [])):
                raise EmbeddingFilesError(f"Dimensions incohérentes dans {vectors_path}.")
            if matrix.shape[1] == 0 or not np.isfinite(matrix).all():
                raise EmbeddingFilesError(f"Vecteurs invalides dans {vectors_path}.")
            if dimension is None:
                dimension = int(matrix.shape[1])
            elif matrix.shape[1] != dimension:
                raise EmbeddingFilesError("Les dimensions des embeddings ne sont pas identiques.")

            norms = np.linalg.norm(matrix, axis=1)
            if np.any(norms == 0) or not np.allclose(norms, 1.0, atol=1e-3):
                raise EmbeddingFilesError("Les vecteurs doivent être normalisés en norme L2.")

            document_metadata = manifest.get("metadata", {})
            document_id = manifest.get("document_id")
            if not isinstance(document_id, str) or not document_id:
                raise EmbeddingFilesError(f"document_id absent dans {manifest_path}.")

            for item in manifest["items"]:
                if not isinstance(item, dict) or not item.get("chunk_id") or not item.get("text"):
                    raise EmbeddingFilesError(f"Métadonnées de chunk invalides dans {manifest_path}.")
                records.append({
                    "document_id": document_id,
                    "chunk_id": item["chunk_id"],
                    "chunk_index": item.get("chunk_index"),
                    "page_number": item.get("page_number"),
                    "text": item["text"],
                    "metadata": document_metadata,
                })
            matrices.append(np.asarray(matrix, dtype=np.float32))

        if not matrices:
            raise EmbeddingFilesError("Aucun embedding exploitable trouvé dans data/embeddings.")
        return np.ascontiguousarray(np.vstack(matrices), dtype=np.float32), records, dimension

    def build_index(self) -> Dict[str, Any]:
        faiss = self._faiss()
        matrix, records, dimension = self._collect_embeddings()
        index = faiss.IndexFlatIP(dimension)
        index.add(matrix)

        manifest = {
            "index_version": "1.0.0",
            "index_type": "IndexFlatIP",
            "similarity_metric": "cosine",
            "model_name": self.model_name,
            "dimension": dimension,
            "vector_count": len(records),
            "created_from": "data/embeddings",
            "items": records,
        }
        temp_index = self.index_path.with_suffix(".faiss.tmp")
        temp_manifest = self.manifest_path.with_suffix(".json.tmp")
        try:
            faiss.write_index(index, str(temp_index))
            temp_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_index.replace(self.index_path)
            temp_manifest.replace(self.manifest_path)
        except OSError as exc:
            temp_index.unlink(missing_ok=True)
            temp_manifest.unlink(missing_ok=True)
            raise EmbeddingFilesError(f"Impossible d'enregistrer l'index FAISS : {exc}") from exc

        return {
            "status": "built",
            "index_path": self.index_path.relative_to(self.data_root).as_posix(),
            "vector_count": len(records),
            "dimension": dimension,
            "model_name": self.model_name,
        }

    def _load_encoder(self):
        if self.encoder is not None:
            return self.encoder
        try:
            from sentence_transformers import SentenceTransformer
            kwargs = {"device": self.device} if self.device else {}
            self.encoder = SentenceTransformer(self.model_name, **kwargs)
            return self.encoder
        except Exception as exc:
            raise VectorSearchError(f"Impossible de charger le modèle d'embedding : {exc}") from exc

    def _encode_query(self, query: str, expected_dimension: int) -> np.ndarray:
        if not isinstance(query, str) or not query.strip():
            raise VectorSearchError("La question ne peut pas être vide.")
        try:
            encoder = self._load_encoder()
            try:
                vector = encoder.encode(
                    [query], convert_to_numpy=True, normalize_embeddings=True,
                    show_progress_bar=False,
                )
            except TypeError:
                vector = encoder.encode([query])
            vector = np.asarray(vector, dtype=np.float32)
            if vector.ndim == 1:
                vector = vector.reshape(1, -1)
            if vector.ndim != 2 or vector.shape[0] != 1 or vector.shape[1] != expected_dimension:
                raise VectorSearchError("La dimension du vecteur de la question ne correspond pas à l'index.")
            if not np.isfinite(vector).all():
                raise VectorSearchError("Le vecteur de la question contient des valeurs invalides.")
            norm = np.linalg.norm(vector, axis=1, keepdims=True)
            if np.any(norm == 0):
                raise VectorSearchError("Le modèle a produit un vecteur nul pour la question.")
            return np.ascontiguousarray(vector / norm, dtype=np.float32)
        except VectorSearchError:
            raise
        except Exception as exc:
            raise VectorSearchError(f"Échec de vectorisation de la question : {exc}") from exc

    def search(self, query: str, top_k: int = 5) -> List[VectorSearchResult]:
        if not isinstance(top_k, int) or top_k < 1:
            raise VectorSearchError("top_k doit être un entier supérieur ou égal à 1.")
        if not self.index_path.exists() or not self.manifest_path.exists():
            raise VectorIndexNotFoundError("Index introuvable. Construisez-le d'abord avec --build.")

        faiss = self._faiss()
        manifest = self._load_json(self.manifest_path)
        if manifest.get("model_name") != self.model_name:
            raise VectorSearchError("Le modèle de recherche ne correspond pas au modèle de l'index.")
        dimension = manifest.get("dimension")
        items = manifest.get("items")
        if not isinstance(dimension, int) or not isinstance(items, list):
            raise EmbeddingFilesError("Manifeste FAISS invalide.")

        try:
            index = faiss.read_index(str(self.index_path))
            if index.ntotal != len(items) or index.d != dimension:
                raise EmbeddingFilesError("L'index FAISS et son manifeste ne sont pas cohérents.")
            query_vector = self._encode_query(query, dimension)
            scores, indices = index.search(query_vector, min(top_k, len(items)))
        except (EmbeddingFilesError, VectorSearchError):
            raise
        except Exception as exc:
            raise VectorSearchError(f"Erreur pendant la recherche FAISS : {exc}") from exc

        results = []
        for rank, (score, item_index) in enumerate(zip(scores[0], indices[0]), start=1):
            if item_index < 0 or item_index >= len(items):
                continue
            item = items[int(item_index)]
            results.append(VectorSearchResult(
                rank=rank,
                score=float(score),
                document_id=item["document_id"],
                chunk_id=item["chunk_id"],
                text=item["text"],
                page_number=item.get("page_number"),
                metadata=item.get("metadata", {}),
            ))
        return results

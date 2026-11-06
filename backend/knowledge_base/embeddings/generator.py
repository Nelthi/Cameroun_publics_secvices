import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from .exceptions import (
    ChunkFileNotFoundError,
    EmbeddingModelError,
    EmbeddingStorageError,
    InvalidChunkFileError,
    InvalidEmbeddingConfigError,
)
from .models import EmbeddingResult


DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class EmbeddingGenerator:
    """Transforme les chunks en vecteurs sémantiques avec Sentence Transformers.

    Le modèle est chargé à la demande. Un encodeur peut être injecté pour les
    tests, sans téléchargement du modèle ni accès réseau.
    """

    def __init__(
        self,
        data_root: str | Path = "data",
        model_name: str = DEFAULT_MODEL,
        batch_size: int = 32,
        device: Optional[str] = None,
        encoder: Any = None,
    ):
        if not isinstance(batch_size, int) or batch_size < 1:
            raise InvalidEmbeddingConfigError("batch_size doit être un entier >= 1.")
        if not isinstance(model_name, str) or not model_name.strip():
            raise InvalidEmbeddingConfigError("model_name ne peut pas être vide.")

        self.data_root = Path(data_root).resolve()
        self.chunks_root = self.data_root / "chunks"
        self.embeddings_root = self.data_root / "embeddings"
        self.embeddings_root.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name.strip()
        self.batch_size = batch_size
        self.device = device
        self.encoder = encoder

    @staticmethod
    def _valid_document_id(document_id: str) -> bool:
        return bool(re.fullmatch(r"DOC-[A-Fa-f0-9]{12}", document_id or ""))

    def _find_chunk_file(self, document_id: str) -> Path:
        if not self._valid_document_id(document_id):
            raise ChunkFileNotFoundError("Identifiant de document invalide.")
        matches = list(self.chunks_root.rglob(f"{document_id}.json"))
        if not matches:
            raise ChunkFileNotFoundError(
                f"Fichier de chunks introuvable pour {document_id}. Exécute d'abord le Text Chunker."
            )
        if len(matches) > 1:
            raise InvalidChunkFileError(
                f"Plusieurs fichiers de chunks portent l'identifiant {document_id}."
            )
        return matches[0]

    def _load_encoder(self):
        if self.encoder is not None:
            return self.encoder
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingModelError(
                "Dépendance manquante. Installe sentence-transformers avec : "
                "python -m pip install -r requirements.txt"
            ) from exc
        try:
            kwargs = {"device": self.device} if self.device else {}
            self.encoder = SentenceTransformer(self.model_name, **kwargs)
            return self.encoder
        except Exception as exc:
            raise EmbeddingModelError(
                f"Impossible de charger le modèle '{self.model_name}' : {exc}"
            ) from exc

    @staticmethod
    def _validate_chunk_payload(payload: Dict[str, Any], document_id: str) -> List[Dict[str, Any]]:
        if not isinstance(payload, dict) or payload.get("document_id") != document_id:
            raise InvalidChunkFileError("L'identifiant du fichier de chunks est incorrect.")
        chunking = payload.get("chunking")
        if not isinstance(chunking, dict) or chunking.get("status") != "chunked":
            raise InvalidChunkFileError("Le document doit avoir le statut 'chunked'.")
        chunks = payload.get("chunks")
        if not isinstance(chunks, list) or not chunks:
            raise InvalidChunkFileError("Aucun chunk disponible pour générer les embeddings.")

        seen_ids = set()
        for chunk in chunks:
            if not isinstance(chunk, dict):
                raise InvalidChunkFileError("Un chunk est mal formé.")
            if chunk.get("document_id") != document_id:
                raise InvalidChunkFileError("Un chunk référence un autre document.")
            chunk_id = chunk.get("chunk_id")
            text = chunk.get("text")
            if not isinstance(chunk_id, str) or not chunk_id.strip() or chunk_id in seen_ids:
                raise InvalidChunkFileError("Identifiant de chunk absent ou dupliqué.")
            if not isinstance(text, str) or not text.strip():
                raise InvalidChunkFileError(f"Texte absent ou vide dans le chunk {chunk_id}.")
            seen_ids.add(chunk_id)
        return chunks

    def _encode(self, texts: List[str]) -> np.ndarray:
        encoder = self._load_encoder()
        try:
            vectors = encoder.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
        except TypeError:
            # Facilite l'utilisation d'encodeurs de test simples.
            vectors = encoder.encode(texts)
        except Exception as exc:
            raise EmbeddingModelError(f"Erreur pendant la génération des embeddings : {exc}") from exc

        try:
            matrix = np.asarray(vectors, dtype=np.float32)
        except (TypeError, ValueError) as exc:
            raise EmbeddingModelError("Le modèle a retourné des vecteurs invalides.") from exc

        if matrix.ndim == 1 and len(texts) == 1:
            matrix = matrix.reshape(1, -1)
        if matrix.ndim != 2 or matrix.shape[0] != len(texts) or matrix.shape[1] == 0:
            raise EmbeddingModelError("Dimensions des embeddings inattendues.")
        if not np.isfinite(matrix).all():
            raise EmbeddingModelError("Les embeddings contiennent des valeurs non finies.")

        # Normalisation L2 explicite : les vecteurs sont prêts pour une recherche
        # par similarité cosinus (et pour IndexFlatIP dans FAISS).
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        if np.any(norms == 0):
            raise EmbeddingModelError("Le modèle a produit un vecteur nul.")
        return np.ascontiguousarray(matrix / norms, dtype=np.float32)

    def embed_document(self, document_id: str) -> EmbeddingResult:
        chunk_file = self._find_chunk_file(document_id)
        try:
            payload = json.loads(chunk_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InvalidChunkFileError(f"Impossible de lire le fichier de chunks : {exc}") from exc

        chunks = self._validate_chunk_payload(payload, document_id)
        texts = [chunk["text"] for chunk in chunks]
        matrix = self._encode(texts)

        metadata = payload.get("metadata", {})
        domain = str(metadata.get("domain", "unknown"))
        subdomain = str(metadata.get("subdomain", "unknown"))
        # Le chemin est dérivé du chemin réel du fichier source de chunks,
        # plutôt que de valeurs de métadonnées non fiables.
        relative_parent = chunk_file.parent.relative_to(self.chunks_root)
        output_dir = self.embeddings_root / relative_parent / document_id
        output_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "document_id": document_id,
            "source_chunk_file": chunk_file.relative_to(self.data_root).as_posix(),
            "metadata": metadata,
            "embedding": {
                "generator_version": "1.0.0",
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "status": "embedded",
                "model_name": self.model_name,
                "embedding_dimension": int(matrix.shape[1]),
                "embedding_count": int(matrix.shape[0]),
                "dtype": "float32",
                "normalization": "l2",
                "similarity_metric": "cosine",
            },
            "items": [
                {
                    "vector_index": index,
                    "chunk_id": chunk["chunk_id"],
                    "document_id": document_id,
                    "chunk_index": chunk.get("chunk_index"),
                    "page_number": chunk.get("page_number"),
                    "character_count": chunk.get("character_count", len(chunk["text"])),
                    "text": chunk["text"],
                }
                for index, chunk in enumerate(chunks)
            ],
        }

        vectors_path = output_dir / "vectors.npy"
        manifest_path = output_dir / "metadata.json"
        temp_vectors = output_dir / "vectors.npy.tmp"
        temp_manifest = output_dir / "metadata.json.tmp"
        try:
            with temp_vectors.open("wb") as stream:
                np.save(stream, matrix, allow_pickle=False)
            temp_manifest.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temp_vectors.replace(vectors_path)
            temp_manifest.replace(manifest_path)
        except OSError as exc:
            temp_vectors.unlink(missing_ok=True)
            temp_manifest.unlink(missing_ok=True)
            raise EmbeddingStorageError(f"Enregistrement des embeddings impossible : {exc}") from exc

        return EmbeddingResult(
            document_id=document_id,
            status="embedded",
            output_dir=output_dir.relative_to(self.data_root).as_posix(),
            embedding_count=int(matrix.shape[0]),
            embedding_dimension=int(matrix.shape[1]),
            model_name=self.model_name,
        )

    def embed_all(self, domain: Optional[str] = None) -> List[EmbeddingResult]:
        if not self.chunks_root.exists():
            return []
        results = []
        for chunk_file in sorted(self.chunks_root.rglob("DOC-*.json")):
            try:
                payload = json.loads(chunk_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise InvalidChunkFileError(f"Fichier de chunks illisible {chunk_file}: {exc}") from exc
            metadata = payload.get("metadata", {})
            if domain and str(metadata.get("domain", "")).lower() != domain.lower():
                continue
            results.append(self.embed_document(payload.get("document_id", "")))
        return results

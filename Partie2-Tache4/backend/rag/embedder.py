"""Transformation de textes en vecteurs (embeddings).

Aucun LLM ici : le modèle all-MiniLM-L6-v2 est un petit réseau qui
convertit une phrase en 384 nombres. Deux phrases de sens proche donnent
des vecteurs proches.
"""
import numpy as np

from .config import MODEL_NAME


class Embedder:
    def __init__(self, model_name=MODEL_NAME, normalize=True):
        self.model_name = model_name
        # normalize=True : tous les vecteurs ont une longueur 1. La distance L2
        # donne alors le même classement que la similarité cosinus.
        self.normalize = normalize
        self._model = None  # chargé seulement au premier usage (démarrage rapide)

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts, batch_size=32):
        """Renvoie un tableau numpy float32 de forme (len(texts), 384)."""
        texts = list(texts)
        vectors = self.model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize,
            show_progress_bar=len(texts) > 100,
        )
        return np.asarray(vectors, dtype="float32")

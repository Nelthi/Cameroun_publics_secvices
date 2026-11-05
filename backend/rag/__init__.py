"""Module RAG (T4). Point d'entrée pour les agents de la Phase 3 :

    from backend.rag import search
    resultats = search("Quelles sont les pièces pour la CNI ?", top_k=4)
"""
from .config import DEFAULT_TOP_K
from .vector_store import VectorStore

_store = None


def search(query, top_k=DEFAULT_TOP_K):
    """Recherche dans l'index sur disque (chargé une seule fois en mémoire)."""
    global _store
    if _store is None:
        _store = VectorStore.from_disk()
    return _store.search(query, top_k)


def reset_store():
    """À appeler après une reconstruction de l'index pour le recharger."""
    global _store
    _store = None

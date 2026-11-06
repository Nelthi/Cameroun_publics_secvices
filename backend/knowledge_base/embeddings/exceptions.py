class EmbeddingError(Exception):
    """Erreur de base du module d'embeddings."""


class InvalidEmbeddingConfigError(EmbeddingError):
    pass


class ChunkFileNotFoundError(EmbeddingError):
    pass


class InvalidChunkFileError(EmbeddingError):
    pass


class EmbeddingModelError(EmbeddingError):
    pass


class EmbeddingStorageError(EmbeddingError):
    pass

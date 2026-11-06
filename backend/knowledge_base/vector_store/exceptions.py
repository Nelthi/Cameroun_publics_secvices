class VectorStoreError(Exception):
    """Erreur de base du Vector Store."""


class FaissDependencyError(VectorStoreError):
    pass


class EmbeddingFilesError(VectorStoreError):
    pass


class VectorIndexNotFoundError(VectorStoreError):
    pass


class VectorSearchError(VectorStoreError):
    pass


class VectorStoreConfigError(VectorStoreError):
    pass

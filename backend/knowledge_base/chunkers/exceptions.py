class ChunkingError(Exception):
    """Erreur générale lors du découpage d'un document."""


class ProcessedDocumentNotFoundError(ChunkingError):
    """Le document traité est introuvable."""


class InvalidChunkingConfigError(ChunkingError):
    """La configuration du découpage est invalide."""


class InvalidProcessedDocumentError(ChunkingError):
    """Le JSON produit par le Document Processor est invalide."""

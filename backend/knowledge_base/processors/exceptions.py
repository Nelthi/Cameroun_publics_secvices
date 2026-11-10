class DocumentProcessingError(Exception):
    """Erreur générale pendant le traitement d'un document."""


class DocumentNotFoundError(DocumentProcessingError):
    """Le document demandé n'existe pas dans le registre du Collector."""


class SourceFileError(DocumentProcessingError):
    """Le fichier brut est absent ou incohérent avec ses métadonnées."""


class TextExtractionError(DocumentProcessingError):
    """Le texte du document n'a pas pu être extrait."""

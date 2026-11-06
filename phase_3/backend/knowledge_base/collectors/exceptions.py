"""Exceptions du module T1 — Ingestion and Storage."""


class CollectorError(Exception):
    """Erreur de base pour l'ingestion de documents."""


class UnsupportedFormatError(CollectorError):
    """Extension de fichier non supportée."""


class InvalidDocumentError(CollectorError):
    """Fichier vide, trop volumineux, illisible ou signature invalide."""


class MetadataValidationError(CollectorError):
    """Métadonnées manquantes ou invalides."""

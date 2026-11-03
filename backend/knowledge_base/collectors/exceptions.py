class CollectorError(Exception):
    """Base exception for document collection errors."""


class UnsupportedFormatError(CollectorError):
    """Raised when a file extension is not supported."""


class InvalidDocumentError(CollectorError):
    """Raised when a file is empty, too large, or has an invalid signature."""


class DuplicateDocumentError(CollectorError):
    """Raised when the same file content has already been imported."""


class MetadataValidationError(CollectorError):
    """Raised when required metadata is missing or invalid."""

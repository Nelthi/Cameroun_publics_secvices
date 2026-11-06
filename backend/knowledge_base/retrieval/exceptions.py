class RetrievalError(Exception):
    """Erreur générale du moteur de récupération."""


class RetrievalConfigError(RetrievalError):
    """Configuration invalide du moteur de récupération."""


class EmptyQueryError(RetrievalError):
    """Question absente ou vide."""

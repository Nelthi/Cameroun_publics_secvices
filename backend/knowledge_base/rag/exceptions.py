class RagError(Exception):
    """Erreur de base du pipeline RAG."""


class RagConfigError(RagError):
    """Configuration du pipeline ou du modèle invalide."""


class LLMProviderError(RagError):
    """Le fournisseur LLM n'a pas pu produire une réponse."""

"""Textes fixes (français / anglais) utilisés par les agents.

Le français est la langue par défaut ; toute langue inconnue retombe sur le français.
"""
from __future__ import annotations

SUPPORTED_LANGUAGES = ("fr", "en")
DEFAULT_LANGUAGE = "fr"

# Phrase canonique quand les documents ne permettent pas de répondre.
# Le prompt demande au LLM de la reprendre mot pour mot ; l'agent la détecte ensuite.
NO_ANSWER = {
    "fr": "Je ne dispose pas d'information officielle sur ce point dans les documents consultés.",
    "en": "I do not have official information on this point in the documents consulted.",
}

LANGUAGE_NAME = {"fr": "français simple", "en": "English (plain language)"}

GREETING = {
    "fr": (
        "Bonjour ! Je suis l'assistant des démarches administratives du Cameroun. "
        "Je peux vous expliquer les étapes, les pièces à fournir et les délais, en commençant "
        "par la carte nationale d'identité (CNI). Posez-moi votre question. "
        "Je vous oriente, mais l'administration reste l'autorité officielle."
    ),
    "en": (
        "Hello! I am the assistant for administrative procedures in Cameroon. "
        "I can explain the steps, the documents to provide and the deadlines, starting with "
        "the national identity card (CNI). Ask me your question. "
        "I guide you, but the administration remains the official authority."
    ),
}

CLARIFICATION = {
    "fr": (
        "Pouvez-vous préciser votre demande ? Par exemple : quelle démarche vous intéresse "
        "(première CNI, renouvellement, perte ou vol, retrait de la carte...) ?"
    ),
    "en": (
        "Could you clarify your request? For example: which procedure are you interested in "
        "(first ID card, renewal, loss or theft, card collection...)?"
    ),
}

OUT_OF_SCOPE = {
    "fr": (
        "Je ne peux répondre qu'aux questions sur les démarches administratives (pour l'instant, "
        "surtout la carte nationale d'identité). Pouvez-vous reformuler votre question dans ce cadre ?"
    ),
    "en": (
        "I can only answer questions about administrative procedures (for now, mainly the national "
        "identity card). Could you rephrase your question within this scope?"
    ),
}

# Libellés des sections quand plusieurs agents sont fusionnés (merge_drafts).
SECTION_LABEL = {
    "fr": {
        "procedure": "Procédure",
        "juridique": "Textes officiels",
        "donnees_personnelles": "Données personnelles",
        "anti_fraude": "Vigilance anti-fraude",
    },
    "en": {
        "procedure": "Procedure",
        "juridique": "Official texts",
        "donnees_personnelles": "Personal data",
        "anti_fraude": "Fraud warning",
    },
}


def normalize_language(language: str | None) -> str:
    """'fr', 'FR', 'fr-CM', 'en_US' -> 'fr' / 'en' ; inconnu ou vide -> 'fr'."""
    if not isinstance(language, str):
        return DEFAULT_LANGUAGE
    code = language.strip().lower().replace("_", "-").split("-")[0]
    return code if code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE

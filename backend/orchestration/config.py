"""Configuration T1 Phase 3 — mots-clés et règles déterministes.

Toute modification des listes change le comportement de classification.
Les motifs sont comparés sur le texte nettoyé puis « foldé » (sans accents),
en minuscules.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Intentions — priorité du plus spécifique / bloquant au plus générique.
#
# Stratégie documentée :
# 1. On score chaque intention via ses mots-clés (match sous-chaîne).
# 2. Si plusieurs intentions ont un score > 0, INTENT_PRIORITY départage
#    EN PREMIER : l'intention la plus spécifique l'emporte dès qu'elle matche,
#    même si une intention plus générique a plus de mots-clés.
#    Ordre : donnees_personnelles > juridique > procedure > accueil > hors_sujet.
# 3. À priorité égale (cas théorique), le score le plus élevé gagne.
# 4. Si aucun mot-clé ne matche → hors_sujet.
# ---------------------------------------------------------------------------

INTENT_PRIORITY: Final[tuple[str, ...]] = (
    "donnees_personnelles",
    "juridique",
    "procedure",
    "accueil",
    "hors_sujet",
)

INTENT_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "accueil": (
        "bonjour",
        "bonsoir",
        "salut",
        "hello",
        "merci",
        "qui es tu",
        "qui etes vous",
        "presentation",
        "aide moi",
        "besoin d aide",
        "que peux tu",
        "que pouvez vous",
    ),
    "procedure": (
        "comment obtenir",
        "comment faire",
        "quelles demarches",
        "quelle demarche",
        "pieces a fournir",
        "documents a fournir",
        "dossier",
        "procedure",
        "demarche",
        "obtenir",
        "renouveler",
        "renouvellement",
        "inscription",
        "depot",
        "delai",
        "combien de temps",
        "ou deposer",
        "ou faire",
        "formulaire",
        "cni",
        "carte nationale",
        "carte d identite",
        "passeport",
        "acte de naissance",
        "extrait de naissance",
    ),
    "juridique": (
        "loi",
        "decret",
        "arrete",
        "texte de loi",
        "base legale",
        "juridique",
        "droit",
        "obligation legale",
        "article",
        "reglementation",
        "reglement",
        "sanction",
        "illegal",
        "autorise par la loi",
    ),
    "donnees_personnelles": (
        "donnees personnelles",
        "vie privee",
        "confidentialite",
        "rgpd",
        "protection des donnees",
        "mes informations",
        "mes donnees",
        "supprimer mes donnees",
        "acces a mes donnees",
        "consentement",
        "numero cni",
        "numero de piece",
    ),
    "hors_sujet": (
        "recette",
        "cuisine",
        "football",
        "match",
        "blague",
        "horoscope",
        "crypto",
        "bitcoin",
        "film",
        "musique",
        "weather",
        "meteo",
        "jeu video",
    ),
}

# Domaines / sous-domaines — extensible : ajouter une clé domaine puis
# ses sous-domaines et mots-clés. Si aucun motif ne matche → unknown.
UNKNOWN_DOMAIN: Final[str] = "unknown"
UNKNOWN_SUBDOMAIN: Final[str] = "unknown"

DOMAIN_KEYWORDS: Final[dict[str, dict[str, tuple[str, ...]]]] = {
    "public_services": {
        "national_identity_card": (
            "cni",
            "carte nationale d identite",
            "carte nationale",
            "carte d identite",
            "identite nationale",
        ),
        "passport": (
            "passeport",
            "passport",
        ),
        "birth_certificate": (
            "acte de naissance",
            "extrait de naissance",
        ),
    },
    # Exemples d'extension future (mots-clés vides = non actifs) :
    # "education": {"exams": ("baccalaureat", "concours")},
    # "health": {"insurance": ("caisse", "assurance maladie")},
}

# Agents indicatifs alignés sur les exemples du guide Phase 3
# (à confirmer avec l'équipe T2 — ne pas considérer comme liste finale).
# Sélection : 1 à 3 agents ; hors_sujet → liste vide.
MAX_AGENTS: Final[int] = 3

INTENT_TO_AGENTS: Final[dict[str, tuple[str, ...]]] = {
    "accueil": ("accueil",),
    "procedure": ("procedure",),
    "juridique": ("juridique",),
    "donnees_personnelles": ("donnees_personnelles",),
    "hors_sujet": (),
}

# Agents secondaires possibles si une intention secondaire matche aussi
# (score > 0), dans cet ordre de préférence.
SECONDARY_INTENT_AGENTS: Final[tuple[str, ...]] = (
    "juridique",
    "procedure",
    "donnees_personnelles",
    "accueil",
)

# ---------------------------------------------------------------------------
# Clarification — questions vagues / incomplètes (≠ hors sujet).
# ---------------------------------------------------------------------------
# Une question hors sujet claire ("recette", "football") n'est PAS une
# clarification : needs_clarification=false, intent=hors_sujet.
# Une question on-topic mais trop floue demande une précision.

VAGUE_QUESTION_PATTERNS: Final[tuple[str, ...]] = (
    "comment faire",
    "comment faire ?",
    "j ai un probleme",
    "j'ai un probleme",
    "jai un probleme",
    "je veux le document",
    "je veux mon document",
    "aide moi",
    "aidez moi",
    "c est quoi",
    "et apres",
    "et ensuite",
    "je ne sais pas",
    "je suis perdu",
    "besoin d aide",
    "que faire",
    "que dois je faire",
)

# Seuil de tokens : en dessous, si aucun domaine n'est détecté → clarification.
CLARIFICATION_MIN_TOKENS: Final[int] = 4

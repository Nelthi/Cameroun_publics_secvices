"""Règles métier : sous-domaine, document à chercher, institution probable.

Tout est regroupé ici pour être relu et corrigé par l'équipe en un seul endroit.
Les institutions sont des HYPOTHÈSES, toujours suffixées « (à confirmer) » dans le rapport.
"""
from __future__ import annotations

import re

from .text import concepts, fold

DEFAULT_DOMAIN = "public_services"
DEFAULT_SUBDOMAIN = "general"
TO_CONFIRM = "à confirmer"

# (sous-domaine, motif sur le texte plié). Premier motif qui correspond = sous-domaine retenu.
# La CNI passe avant l'état civil : la CNI exige elle-même un acte de naissance.
SUBDOMAIN_RULES = [
    ("national_identity_card", r"\b(cni|identite|identitaires?|enrolement|preenrolement|idcam)\b"),
    ("passport", r"\bpasseports?\b"),
    ("driving_license", r"\bpermis\b"),
    ("civil_status", r"\b(acte de naissance|naissance|mariage|deces|etat civil|livret de famille|mairie)\b"),
    ("taxes", r"\b(impots?|fiscal\w*|taxes?|dgi|contribuables?|niu)\b"),
    ("public_treasury", r"\b(tresor|tresorpay|minfi|compte unique)\b"),
    ("personal_data_protection", r"\b(donnees personnelles|protection des donnees|vie privee|rgpd)\b"),
]

# Institution probable par sous-domaine (à confirmer par l'équipe avant collecte).
INSTITUTION_BY_SUBDOMAIN = {
    "national_identity_card": "DGSN",
    "passport": "DGSN",
    "civil_status": "Mairies (état civil)",
    "taxes": "MINFI / Direction Générale des Impôts",
    "public_treasury": "Trésor public / MINFI",
    "personal_data_protection": "Présidence de la République",
}

# (concept, document à chercher). Premier concept présent = document suggéré.
DOCUMENT_RULES = [
    ("FRAIS", "barème des frais"),
    ("DELAI", "texte ou note officielle fixant les délais"),
    ("PIECES", "liste officielle des pièces à fournir"),
    ("PERTE", "procédure officielle en cas de perte ou de vol"),
    ("RENOUVELLEMENT", "procédure officielle de renouvellement"),
    ("RETRAIT", "procédure officielle de retrait du titre"),
    ("LIEU", "liste des centres ou postes avec adresses et horaires"),
    ("DONNEES", "texte sur la protection des données personnelles"),
    ("TEXTE", "texte réglementaire (loi, décret ou arrêté)"),
    ("FRAUDE", "communiqué ou alerte officielle contre la fraude"),
]
DEFAULT_DOCUMENT = "fiche officielle décrivant la procédure"


def infer_subdomain(text: str) -> str:
    """Sous-domaine déduit de mots-clés, « general » si aucun ne correspond."""
    folded = fold(text)
    for subdomain, pattern in SUBDOMAIN_RULES:
        if re.search(pattern, folded):
            return subdomain
    return DEFAULT_SUBDOMAIN


def suggest_document(texts: list[str]) -> str:
    """Type de document à chercher, d'après les concepts présents dans les libellés du sujet."""
    found = set().union(*(concepts(t) for t in texts)) if texts else set()
    for concept, document in DOCUMENT_RULES:
        if concept in found:
            return document
    return DEFAULT_DOCUMENT


def suggest_institution(subdomain: str) -> str:
    """« DGSN (à confirmer) » si le sous-domaine est connu, sinon « à confirmer »."""
    institution = INSTITUTION_BY_SUBDOMAIN.get(subdomain)
    return f"{institution} ({TO_CONFIRM})" if institution else TO_CONFIRM

"""Normalisation de texte, similarité entre sujets et masquage des données personnelles.

Deux libellés qui parlent du même sujet (« coût du permis », « Combien coûte le permis de
conduire ? », « frais du permis ») doivent tomber dans la même lacune. On y arrive sans modèle :
  1. minuscules, sans accents ni ponctuation ;
  2. mots vides retirés (« le », « combien », « comment »...) ;
  3. synonymes ramenés à un concept (coût, prix, tarif, montant... -> FRAIS) ;
  4. pluriels et « e » final retirés ;
  5. comparaison des ensembles de mots (Jaccard, avec tolérance quand un libellé en contient un autre).
"""
from __future__ import annotations

import re
import unicodedata

# --- Concepts (synonymes ramenés à une étiquette) ---------------------------------------------
_CONCEPT_WORDS = {
    "FRAIS": "frais cout couts coute couter coutent prix tarif tarifs tarification montant montants "
             "payer paye paiement paiements payement redevance droit droits timbre bareme gratuit gratuite",
    "DELAI": "delai delais duree temps jours heures semaines",
    "PIECES": "piece pieces document documents dossier dossiers justificatif justificatifs papier papiers",
    "PERTE": "perte perdu perdue perdre vol vole volee deterioration deteriore deterioree",
    "RENOUVELLEMENT": "renouvellement renouveler renouvelle perime perimee expire expiree expiration",
    "RETRAIT": "retrait retirer retire recuperer recuperation procuration",
    "LIEU": "lieu centre centres poste postes adresse adresses localisation horaire horaires bureau "
            "bureaux guichet depot deposer",
    "TEXTE": "loi lois decret decrets arrete arretes texte textes article articles reglementation "
             "legislation juridique legal reglement",
    "FRAUDE": "fraude fraudes arnaque arnaques escroquerie escroc escrocs faux fausse intermediaire "
              "intermediaires brouteur",
    "DONNEES": "donnees donnee confidentialite rgpd",
    "CNI": "cni identite identitaire identitaires idcam",
}
CONCEPT_OF = {word: label for label, words in _CONCEPT_WORDS.items() for word in words.split()}

STOPWORDS = frozenset("""
le la les l un une des de du d en et ou a au aux pour par sur dans avec sans est sont ce cet cette ces
mon ma mes ton ta tes son sa ses notre nos votre vos leur leurs je tu il elle on nous vous ils elles
me te se qui que quoi dont quel quelle quels quelles combien comment pourquoi quand puis peut peux
peuvent faut dois doit dit faire obtenir avoir etre ai ete y pas ne plus moins tres bien svp bonjour
bonsoir merci voudrais veux souhaite souhaiterais possible information informations renseignement
renseignements sujet si ca cela quelqu quelqu'un c s n t j m qu il y
""".split())

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'", "´": "'"})
_CNI_PHRASE = re.compile(r"\bcarte\s+(?:nationale\s+)?d\s*identite\b")


def fold(text: str) -> str:
    """Minuscules, sans accents, tout ce qui n'est pas lettre ou chiffre devient un espace."""
    text = unicodedata.normalize("NFKD", str(text).translate(_APOSTROPHES).casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def _stem(word: str) -> str:
    if len(word) > 4 and word[-1] in "sx":
        word = word[:-1]
    if len(word) > 4 and word.endswith("e"):
        word = word[:-1]
    return word


def tokens(text: str) -> frozenset[str]:
    """Ensemble de mots significatifs (concepts en MAJUSCULES, autres mots racinisés)."""
    folded = _CNI_PHRASE.sub("cni", fold(text))
    result = set()
    for word in folded.split():
        if word in STOPWORDS or (len(word) < 2 and not word.isdigit()):
            continue
        result.add(CONCEPT_OF.get(word) or _stem(word))
    return frozenset(result)


def concepts(text: str) -> frozenset[str]:
    """Seulement les concepts métier présents dans le texte (FRAIS, DELAI, PIECES...)."""
    return frozenset(t for t in tokens(text) if t.isupper() and t.isalpha())


def topic_key(token_set: frozenset[str], fallback: str = "") -> str:
    """Clé stable d'un sujet : mots triés. Texte plié si aucun mot significatif."""
    return " ".join(sorted(token_set)) if token_set else fold(fallback)


def similarity(a: frozenset[str], b: frozenset[str]) -> float:
    """Jaccard, relevé quand le plus court des deux (>= 2 mots) est contenu dans l'autre."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    jaccard = inter / len(a | b)
    if min(len(a), len(b)) >= 2:
        return max(jaccard, 0.8 * inter / min(len(a), len(b)))
    return jaccard


# --- Données personnelles -----------------------------------------------------------------------
MASK = "[NUMERO_MASQUE]"
EMAIL_MASK = "[EMAIL_MASQUE]"
_PHONE_PATTERNS = (
    re.compile(r"(?<!\d)(?:\+|00)\s?237[\s.\-]?\d(?:[\s.\-]?\d){7,8}(?!\d)"),
    re.compile(r"(?<!\d)6(?:[\s.\-]?\d){8}(?!\d)"),
    re.compile(r"(?<!\d)\d{8,}(?!\d)"),
)
_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")


def mask_sensitive(text: str) -> str:
    """Masque téléphones, longs numéros (CNI, dossier) et e-mails : un rapport ne doit rien divulguer."""
    for pattern in _PHONE_PATTERNS:
        text = pattern.sub(MASK, text)
    return _EMAIL.sub(EMAIL_MASK, text)


def clean_text(text, max_len: int) -> str:
    """Espaces normalisés, données personnelles masquées, longueur bornée."""
    text = mask_sensitive(re.sub(r"\s+", " ", str(text)).strip())
    return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "…"

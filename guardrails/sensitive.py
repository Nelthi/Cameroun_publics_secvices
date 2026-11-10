"""Détection et masquage des données personnelles sensibles."""
import re

MASQUE = "[donnée masquée]"

# Numéro de téléphone camerounais : 9 chiffres commençant par 6 (mobile) ou 2 (fixe), préfixe +237 facultatif.
_TEL = re.compile(r"(?<!\d)(?:\+?237[\s.-]?)?[62]\d{2}(?:[\s.-]?\d{2}){3}(?!\d)")
# Numéro de CNI : suite de 8 à 12 chiffres annoncée par un mot-clé (format exact à confirmer).
_CNI = re.compile(
    r"(?i)(?:\bcni\b|carte(?:\s+nationale)?\s+d['’]identité|numéro|n°)\D{0,25}?(\d[\d\s.-]{6,16}\d)"
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def chiffres(s):
    return re.sub(r"\D", "", s)


def trouver(texte):
    """Retourne la liste des (type, extrait, début, fin) de données sensibles trouvées."""
    trouves = []
    for m in _EMAIL.finditer(texte):
        trouves.append(("email", m.group(0), m.start(), m.end()))
    for m in _TEL.finditer(texte):
        trouves.append(("telephone", m.group(0), m.start(), m.end()))
    for m in _CNI.finditer(texte):
        trouves.append(("numero_cni", m.group(1), m.start(1), m.end(1)))
    return trouves


def masquer(texte, autorises=frozenset()):
    """Masque les données sensibles de `texte`.

    `autorises` : chiffres normalisés de numéros qui apparaissent dans les documents
    officiels cités (ex : numéro vert d'une institution) et qu'on laisse donc passer.
    Retourne (texte_masque, liste_des_types_trouves).
    """
    types, spans = [], []
    for typ, extrait, a, b in trouver(texte):
        if typ != "email" and chiffres(extrait) in autorises:
            continue
        spans.append((a, b))
        types.append(typ)
    for a, b in sorted(spans, reverse=True):
        texte = texte[:a] + MASQUE + texte[b:]
    return texte, types

"""Logique des guardrails de T3 (Phase 3).

Entrée : le brouillon de T2 + la question d'origine (+ les passages de la Phase 2, facultatif).
Sortie : un dictionnaire conforme au contrat T3 (voir README.md).
"""
import re
import unicodedata

from .sensitive import chiffres, masquer, trouver

SEUIL_SCORE = 0.35

_MARQUEUR = re.compile(r"\[(\d+)\]")
_NOMBRE = re.compile(r"\d[\d\s.,]*\d|\d")
_PAS_SAIT = re.compile(
    r"(?i)\b(je ne (dispose|sais|peux|trouve)|aucune information|pas d['’]information|"
    r"n['’]est pas disponible|ne sont pas disponibles|je suis désolé)"
)
_ABREV = re.compile(r"(?i)(?:^|\s)(?:m|mme|mlle|dr|pr|art|no|cf|ex|tél|etc)\.$")
_EXEMPT = re.compile(r"(?i)^\s*(bonjour|bonsoir|merci|n['’]hésitez|cordialement|voici)\b")

MSG_REFUS = (
    "Je ne dispose pas d'informations suffisamment fiables dans les documents officiels "
    "pour répondre à cette question. Pour une réponse sûre, rapprochez-vous de l'institution concernée."
)
MSG_PARTIEL = (
    "Note : certaines informations n'ont pas pu être confirmées dans les documents officiels "
    "et ont été retirées. Vérifiez auprès de l'institution concernée."
)
MSG_SENSIBLE = (
    "Attention : ne partagez jamais votre numéro de CNI, votre téléphone ou d'autres données "
    "personnelles dans ce service."
)


def _norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _phrases(texte):
    """Découpe le brouillon en lignes, chaque ligne en phrases."""
    lignes = []
    for ligne in texte.split("\n"):
        ligne = ligne.strip()
        if ligne:
            morceaux = []
            for p in re.split(r"(?<=[.!?])\s+", ligne):
                if morceaux and _ABREV.search(morceaux[-1]):
                    morceaux[-1] += " " + p  # « M. Ndi », « art. 5 » : pas une fin de phrase
                elif p.strip():
                    morceaux.append(p)
            lignes.append(morceaux)
    return lignes


def _est_affirmation(phrase):
    """Une phrase à vérifier : assez longue, pas une formule de politesse ni une introduction."""
    sans = _MARQUEUR.sub("", phrase).strip()
    if sans.endswith(":") or _EXEMPT.match(sans):
        return False
    return len(sans.split()) >= 4


def _supportee(phrase, textes):
    """Vérifie que les chiffres et les mots clés de la phrase se retrouvent dans les passages cités."""
    sans = _MARQUEUR.sub("", phrase)
    brut = " ".join(textes)
    nombres_pass = {chiffres(n) for n in _NOMBRE.findall(brut)}
    for n in _NOMBRE.findall(sans):
        if chiffres(n) and chiffres(n) not in nombres_pass:
            return False
    mots = {w[:5] for w in re.findall(r"[a-zà-ÿ]{5,}", _norm(sans))}
    if not mots:
        return True
    mots_pass = {w[:5] for w in re.findall(r"[a-zà-ÿ]{5,}", _norm(brut))}
    return len(mots & mots_pass) / len(mots) >= 0.5


def verifier_brouillon(draft, question, passages=None, seuil=SEUIL_SCORE):
    """Applique tous les contrôles et retourne la sortie T3.

    draft     : sortie de T2 (request_id, answer_draft, citations, retrieval)
    question  : question d'origine du citoyen
    passages  : liste facultative de {chunk_id, text} renvoyée par search() ; sans elle, on ne
                peut pas vérifier que les citations existent ni que le contenu est fondé.
    """
    rid = draft["request_id"]
    texte = (draft.get("answer_draft") or "").strip()
    citations = draft.get("citations") or []
    top_score = (draft.get("retrieval") or {}).get("top_score") or 0.0
    n_chunks = (draft.get("retrieval") or {}).get("n_chunks") or 0
    par_id = {p["chunk_id"]: p["text"] for p in passages} if passages is not None else None

    gaps = []
    sujet = " ".join(question.split())[:80]

    def sortie(status, reponse, cits, checks):
        for g in gaps:  # jamais de donnée personnelle dans la table des lacunes
            g["topic"] = masquer(g["topic"])[0]
        return {"request_id": rid, "status": status, "final_answer": reponse,
                "citations": cits, "checks": checks, "gaps": gaps}

    score_ok = top_score >= seuil and n_chunks > 0
    pas_sait = bool(_PAS_SAIT.search(texte)) or not texte
    base = {"grounded": False, "has_citations": False, "score_ok": score_ok, "no_sensitive_data": True}

    # Donnée sensible dans la question : on le note, on ne la répète jamais.
    sensible_question = bool(trouver(question))

    if not score_ok or pas_sait:
        gaps.append({"topic": sujet,
                     "reason": "no_relevant_chunk" if (n_chunks == 0 or pas_sait) else "low_score"})
        base["no_sensitive_data"] = not sensible_question
        rep = MSG_REFUS + ("\n\n" + MSG_SENSIBLE if sensible_question else "")
        return sortie("refused", rep, [], base)

    # Chiffres des numéros présents dans les documents cités : ce sont des numéros officiels, on les laisse.
    autorises = frozenset()
    if par_id is not None:
        autorises = frozenset(chiffres(m[1]) for t in par_id.values() for m in trouver(t))

    gardees, retirees, refs_utilisees = [], [], set()
    toutes_citees, toutes_valides = True, True
    for ligne in _phrases(texte):
        sortie_ligne = []
        for ph in ligne:
            if not _est_affirmation(ph):
                sortie_ligne.append(ph)
                continue
            refs = [int(n) for n in _MARQUEUR.findall(ph)]
            if not refs:
                retirees.append((ph, "no_citation"))
                toutes_citees = False
                continue
            valides = [n for n in refs if 1 <= n <= len(citations)
                       and (par_id is None or citations[n - 1]["chunk_id"] in par_id)]
            if len(valides) != len(refs):
                retirees.append((ph, "invalid_citation"))
                toutes_valides = False
                continue
            if par_id is not None and not _supportee(ph, [par_id[citations[n - 1]["chunk_id"]] for n in valides]):
                retirees.append((ph, "unsupported_claim"))
                toutes_valides = False
                continue
            refs_utilisees.update(valides)
            sortie_ligne.append(ph)
        if sortie_ligne:
            gardees.append(" ".join(sortie_ligne))

    reste = "\n".join(gardees)
    for ph, raison in retirees:
        propre = re.sub(r"\s+([.,;:!?])", r"\1", _MARQUEUR.sub("", ph)).strip()
        gaps.append({"topic": propre[:80], "reason": raison})

    checks = {"grounded": toutes_valides, "has_citations": toutes_citees and bool(refs_utilisees),
              "score_ok": True, "no_sensitive_data": True}

    if not refs_utilisees:  # plus aucune affirmation vérifiée
        if not gaps:
            gaps.append({"topic": sujet, "reason": "no_citation"})
        checks["has_citations"] = False
        checks["no_sensitive_data"] = not sensible_question
        return sortie("refused", MSG_REFUS + ("\n\n" + MSG_SENSIBLE if sensible_question else ""), [], checks)

    reste, types = masquer(reste, autorises)
    _, types_brouillon = masquer(texte, autorises)  # y compris dans les phrases retirées
    sensible = bool(types) or bool(types_brouillon) or sensible_question
    checks["no_sensitive_data"] = not sensible
    notes = []
    if retirees:
        notes.append(MSG_PARTIEL)
    if sensible:
        notes.append(MSG_SENSIBLE)
    status = "approved" if not retirees and not sensible else "partial"
    final = reste + ("\n\n" + "\n".join(notes) if notes else "")
    cits = [citations[n - 1] for n in sorted(refs_utilisees)]
    return sortie(status, final, cits, checks)

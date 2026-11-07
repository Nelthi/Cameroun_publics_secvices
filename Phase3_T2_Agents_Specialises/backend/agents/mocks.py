"""Faux search() et faux LLM pour tester T2 seul (règle d'or du guide : on simule les entrées).

- fake_search(query, top_k) : même format que backend.rag.search (Phase 2), mais sur un petit
  corpus fixe. Les passages « CNI » reprennent le contenu de la plaquette officielle DGSN
  (01_CNI/Plaquette-20-Mai-2025-FR-ok.pdf) ; les passages marqués [EXEMPLE FICTIF] sont inventés
  pour tester les agents « données personnelles » et « anti-fraude ».
- FakeLLM : renvoie une réponse fixe (ou une suite de réponses) et garde les prompts reçus.
"""
from __future__ import annotations

import re
import unicodedata

MOCK_PASSAGES = [
    {"chunk_id": "DOC-MOCKCNI-C001", "document_id": "DOC-MOCKCNI", "source_page": 1,
     "text": "Pré-enrôlement en ligne : allez sur le site https://www.idcam.cm, choisissez votre langue "
             "(français ou anglais), entrez votre adresse e-mail ou votre numéro de téléphone, puis "
             "validez le code reçu par SMS ou par mail. Remplissez la fiche d'informations, payez les "
             "frais (Yoomee, MTN Mobile Money, Orange Money...) puis choisissez le lieu et la date "
             "d'enrôlement. Vous avez le droit de changer votre date d'enrôlement physique une seule fois."},
    {"chunk_id": "DOC-MOCKCNI-C002", "document_id": "DOC-MOCKCNI", "source_page": 1,
     "text": "Enrôlement physique : présentez-vous au centre d'enrôlement le jour choisi, muni de votre "
             "fiche d'informations, de vos pièces justificatives certifiées et de leurs originaux. "
             "Les fonctionnaires de Police vérifient votre dossier, prennent vos données biométriques "
             "(photo, empreintes digitales) et numérisent vos pièces. Vous recevez un récépissé de dépôt."},
    {"chunk_id": "DOC-MOCKCNI-C003", "document_id": "DOC-MOCKCNI", "source_page": 1,
     "text": "Après validation, s'il n'y a pas de rejet, votre Carte Nationale d'Identité est produite "
             "en 48 heures. En cas de rejet, vous êtes immédiatement notifié par mail ou par SMS avec "
             "des précisions sur la conduite à tenir."},
    {"chunk_id": "DOC-MOCKCNI-C004", "document_id": "DOC-MOCKCNI", "source_page": 1,
     "text": "Retrait : le retrait est effectué au poste d'identification ayant enrôlé le demandeur, "
             "contre restitution du titre d'identité provisoire. Le retrait de la CNI est possible par "
             "un tiers muni d'une procuration du demandeur dûment légalisée par les services compétents."},
    {"chunk_id": "DOC-MOCKCNI-C005", "document_id": "DOC-MOCKCNI", "source_page": 2,
     "text": "Cas de première demande : une copie certifiée conforme de l'acte de naissance, de l'extrait "
             "d'acte de naissance ou du jugement supplétif d'acte de naissance ; un certificat de "
             "nationalité signé du Président du Tribunal de Première Instance du lieu d'établissement "
             "de la carte ; une pièce justificative de la profession, le cas échéant."},
    {"chunk_id": "DOC-MOCKCNI-C006", "document_id": "DOC-MOCKCNI", "source_page": 2,
     "text": "Coût de la CNI : carte nationale d'identité, 10.000 FCFA. La validité de la carte nationale "
             "d'identité est de dix (10) ans."},
    {"chunk_id": "DOC-MOCKCNI-C007", "document_id": "DOC-MOCKCNI", "source_page": 2,
     "text": "Le Chef de l'Etat a signé le 28 février 2025 deux textes réformant les titres identitaires "
             "au Cameroun. Le premier fixe les caractéristiques et les modalités d'établissement et de "
             "délivrance des titres identitaires ; le second modifie et complète certaines dispositions "
             "relatives au Centre National de Production des Titres Identitaires."},
    {"chunk_id": "DOC-MOCKCNI-C008", "document_id": "DOC-MOCKCNI", "source_page": 2,
     "text": "La délivrance de la Carte Nationale d'Identité peut être suspendue en cas de suspicion de "
             "fraude à la nationalité camerounaise ou de demande tardive. La décision relève du Délégué "
             "Général à la Sûreté Nationale ; le demandeur peut lui adresser une requête."},
    {"chunk_id": "DOC-MOCKDATA-C001", "document_id": "DOC-MOCKDATA", "source_page": 1,
     "text": "[EXEMPLE FICTIF] Les données biométriques et biographiques collectées lors de l'enrôlement "
             "servent uniquement à l'établissement du titre d'identité. Le demandeur peut demander "
             "l'accès aux données qui le concernant."},
    {"chunk_id": "DOC-MOCKFRAUD-C001", "document_id": "DOC-MOCKFRAUD", "source_page": 1,
     "text": "[EXEMPLE FICTIF] Aucun intermédiaire n'est autorisé à faire payer des frais supplémentaires. "
             "Le paiement des frais se fait uniquement par les moyens officiels indiqués sur le site "
             "du pré-enrôlement. Méfiez-vous des personnes qui promettent d'accélérer le dossier."},
]

FIXED_ANSWER = "Réponse de test produite par le faux LLM à partir des passages fournis [1][2]."


def _tokens(text: str) -> set[str]:
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return {t for t in re.findall(r"\w+", text) if len(t) > 2}


def fake_search(query: str, top_k: int = 4) -> list[dict]:
    """Classement par mots communs. Scores factices dans [0, 1], format identique à search()."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("La question ne peut pas être vide")
    if top_k < 1:
        raise ValueError("top_k doit être >= 1")
    q = _tokens(query)
    scored = []
    for passage in MOCK_PASSAGES:
        overlap = len(q & _tokens(passage["text"]))
        scored.append((overlap / max(len(q), 1), passage))
    scored.sort(key=lambda item: -item[0])
    results = []
    for rank, (ratio, passage) in enumerate(scored[:top_k], start=1):
        score = round(min(0.95, 0.15 + 1.6 * ratio), 4)
        results.append({"rank": rank, "score": score, "distance": round(2 * (1 - score), 4), **passage})
    return results


class FakeLLM:
    """Faux llm_generate : réponse fixe, ou suite de réponses (la dernière se répète).

    `answers` peut aussi être une fonction prompt -> texte. Les prompts reçus sont dans `.prompts`.
    """

    def __init__(self, answers=FIXED_ANSWER):
        self.answers = answers
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if callable(self.answers):
            return self.answers(prompt)
        if isinstance(self.answers, (list, tuple)):
            return self.answers[min(len(self.prompts) - 1, len(self.answers) - 1)]
        return self.answers

"""Les agents spécialisés de T2 (un prompt par agent) et l'agent d'accueil."""
from __future__ import annotations

from .base import Agent, make_draft, prepare_question
from .messages import CLARIFICATION, GREETING, OUT_OF_SCOPE, normalize_language


class ProcedureAgent(Agent):
    name = "procedure"
    role = "Procédure"
    instruction = (
        "Votre rôle : expliquer la démarche administrative demandée. Quand les passages le permettent, "
        "présentez dans cet ordre : les étapes à suivre (liste numérotée), les pièces à fournir, "
        "les délais, les frais, le lieu de dépôt ou de retrait. Ne mentionnez que ce qui figure dans les passages."
    )


class JuridiqueAgent(Agent):
    name = "juridique"
    role = "Juridique"
    instruction = (
        "Votre rôle : indiquer les textes juridiques et les instructions officielles applicables "
        "(lois, décrets, arrêtés, articles). Reprenez les références exactement comme dans les passages "
        "(numéro, date, intitulé). N'interprétez pas la loi au-delà du texte et ne donnez pas de conseil "
        "juridique personnalisé."
    )


class DonneesPersonnellesAgent(Agent):
    name = "donnees_personnelles"
    role = "Protection des données"
    query_hint = "protection des données personnelles"
    instruction = (
        "Votre rôle : informer le citoyen sur la protection de ses données personnelles dans la démarche "
        "(quelles données sont collectées, pourquoi, quels sont ses droits), uniquement selon les passages. "
        "Ne demandez jamais de données personnelles au citoyen."
    )


class AntiFraudeAgent(Agent):
    name = "anti_fraude"
    role = "Anti-fraude"
    query_hint = "fraude faux intermédiaires paiement officiel"
    instruction = (
        "Votre rôle : alerter sur les risques de fraude (faux intermédiaires, paiements non officiels, faux sites). "
        "Indiquez les canaux officiels de dépôt ou de paiement UNIQUEMENT s'ils figurent dans les passages, "
        "et invitez à vérifier auprès de l'administration compétente. Ton calme, sans accuser personne."
    )


class AccueilAgent(Agent):
    """Accueil : message fixe, SANS recherche ni LLM (rien à inventer, rien à citer).

    Trois cas, décidés par le plan de routage de T1 :
      - needs_clarification = true -> question de précision ;
      - intent = hors_sujet        -> message de cadrage ;
      - sinon (intent = accueil)   -> message de bienvenue.
    Le brouillon porte meta.kind = "static" : il n'a ni citation ni score (top_score = 0.0).
    """

    name = "accueil"
    role = "Accueil"

    def run(self, question: str, plan: dict, language: str = "fr") -> dict:
        language = normalize_language(language)
        _, meta = prepare_question(question)  # valide la question, signale le masquage
        if plan.get("needs_clarification") is True:
            reason, text = "clarification", CLARIFICATION[language]
        elif plan.get("intent") == "hors_sujet":
            reason, text = "out_of_scope", OUT_OF_SCOPE[language]
        else:
            reason, text = "greeting", GREETING[language]
        meta.update({"kind": "static", "reason": reason, "language": language, "no_answer": False})
        return make_draft(plan["request_id"], self.name, text, [], [], meta)

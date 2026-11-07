"""Faux T1, T2 et T3 pour développer T4 sans attendre les autres membres.

Ils respectent exactement les contrats (voir schemas.py) et renvoient :
- une réponse APPROUVÉE si la question parle de CNI ;
- une réponse REFUSÉE (avec lacune) sinon ;
- needs_clarification = True si la question fait moins de 3 mots.
"""
KEYWORDS_CNI = ("cni", "carte nationale", "identité")


def _is_cni(text):
    return any(k in text.lower() for k in KEYWORDS_CNI)


def route_question(payload: dict) -> dict:  # T1
    q = payload["question"]
    cni = _is_cni(q)
    return {
        "request_id": payload["request_id"],
        "intent": "procedure" if cni else "hors_sujet",
        "domain": "public_services",
        "subdomain": "national_identity_card" if cni else None,
        "agents": ["procedure"] if cni else ["accueil"],
        "needs_clarification": len(q.split()) < 3,
    }


def run_agents(routing: dict, question: str) -> dict:  # T2
    if routing["intent"] == "procedure":
        return {
            "request_id": routing["request_id"],
            "agent": "procedure",
            "answer_draft": "Pour la première demande de CNI, il faut un acte de naissance, "
                            "un certificat de nationalité et deux photos d'identité [1].",
            "citations": [{"chunk_id": "DOC-EXEMPLE-CNI-C001",
                           "document_id": "DOC-EXEMPLE-CNI", "source_page": 1}],
            "retrieval": {"top_score": 0.71, "n_chunks": 4},
        }
    return {
        "request_id": routing["request_id"],
        "agent": routing["agents"][0],
        "answer_draft": "Aucun passage pertinent.",
        "citations": [],
        "retrieval": {"top_score": 0.18, "n_chunks": 4},
    }


def validate_answer(agent_output: dict, question: str) -> dict:  # T3
    ok = agent_output["retrieval"]["top_score"] >= 0.35 and agent_output["citations"]
    if ok:
        return {
            "request_id": agent_output["request_id"],
            "status": "approved",
            "final_answer": agent_output["answer_draft"],
            "citations": agent_output["citations"],
            "checks": {"grounded": True, "has_citations": True,
                       "score_ok": True, "no_sensitive_data": True},
            "gaps": [],
        }
    return {
        "request_id": agent_output["request_id"],
        "status": "refused",
        "final_answer": "Je n'ai pas trouvé cette information dans les documents officiels disponibles.",
        "citations": [],
        "checks": {"grounded": False, "has_citations": False,
                   "score_ok": False, "no_sensitive_data": True},
        "gaps": [{"topic": question[:80], "reason": "no_relevant_chunk"}],
    }

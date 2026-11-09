"""Liaison Phase 3 : branche T1, T2 et T3 sur les « portes » attendues par T4 (app/stages.py).

T4 appelle des fonctions de signature figée (voir app/stages.py) :

    route_question(payload)                -> plan de routage        (T1)
    run_agents(routing, question)          -> UN brouillon           (T2)
    validate_answer(agent_output, question)-> réponse validée        (T3)

Les modules des membres n'ont pas exactement ces signatures :
  * T2 prend (question, plan) et renvoie une LISTE de brouillons (un par agent) ;
    on les assemble avec merge_drafts (fonction fournie par T2 pour cela) ;
  * T3 veut les passages en 3e argument ; T2 les fournit dans retrieval.passages.
Aucun code des membres n'est modifié : ce fichier ne fait que les brancher.

Branchement (fait par `python -m backend.pipeline.serve`, ou à la main) :
    export T1_IMPL="backend.pipeline.phase3:route_question"
    export T2_IMPL="backend.pipeline.phase3:run_agents"
    export T3_IMPL="backend.pipeline.phase3:validate_answer"
"""
from __future__ import annotations

import os
import re

IMPLS = {
    "T1_IMPL": "backend.pipeline.phase3:route_question",
    "T2_IMPL": "backend.pipeline.phase3:run_agents",
    "T3_IMPL": "backend.pipeline.phase3:validate_answer",
}


def route_question(payload: dict) -> dict:  # T1 (Orchestrateur)
    from backend.orchestration import route_question as t1_route

    return t1_route(payload)


def run_agents(routing: dict, question: str) -> dict:  # T2 (Agents)
    from backend.agents import merge_drafts
    from backend.agents import run_agents as t2_run

    _enable_demo_llm_if_requested()
    drafts = t2_run(question, routing, language=routing.get("language") or "fr")
    return merge_drafts(drafts)


def validate_answer(agent_output: dict, question: str) -> dict:  # T3 (Guardrails)
    from guardrails import verifier_brouillon

    passages = (agent_output.get("retrieval") or {}).get("passages")
    return verifier_brouillon(agent_output, question, passages)


# --- Mode démonstration sans LLM (PHASE3_LLM=demo) -------------------------------------------------
# Le choix du LLM est encore à faire en équipe (voir llm.env.example). Pour tester toute la chaîne
# avec la vraie recherche de la Phase 2, ce mode remplace le LLM par une EXTRACTION : la réponse est
# recopiée mot pour mot depuis le passage le plus proche, avec son renvoi [1]. Ce n'est pas une
# génération de texte : à n'utiliser que pour tester ou présenter la chaîne.

def demo_llm(prompt: str) -> str:
    block = re.search(r"PASSAGES\n(.*?)\n\nQUESTION DU CITOYEN", prompt, re.S)
    if not block:
        return "Je n'ai pas trouvé cette information dans les documents officiels fournis."
    first = re.search(r"\[1\] \([^)]*\)\n(.*?)(?:\n\n\[2\]|\Z)", block.group(1), re.S)
    text = re.sub(r"\s+", " ", first.group(1)).strip() if first else ""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?;:])\s+", text) if len(s.split()) >= 5]
    if not sentences:
        return "Je n'ai pas trouvé cette information dans les documents officiels fournis."
    return " ".join(f"{s} [1]" for s in sentences[:2])


def _enable_demo_llm_if_requested() -> None:
    if os.getenv("PHASE3_LLM", "").strip().lower() == "demo" and not os.getenv("LLM_PROVIDER"):
        from backend.agents import set_llm

        set_llm(demo_llm)

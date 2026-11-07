"""Essai manuel des agents.

    # Sans rien installer ni configurer : faux search + faux LLM
    python -m backend.agents.cli "Quels documents pour ma première CNI ?" --mock

    # Avec l'index FAISS de la Phase 2 et le LLM configuré (variables LLM_*)
    python -m backend.agents.cli "Quels documents pour ma première CNI ?" --agents procedure juridique --merge

    # Avec un plan de routage T1 existant
    python -m backend.agents.cli "..." --plan examples/t2/routing_plans_mock.json --plan-index 0 --mock
"""
from __future__ import annotations

import argparse
import json
import sys

from .contract import validate_draft
from .exceptions import AgentError
from .merge import merge_drafts
from .runner import run_agents


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Lance les agents T2 sur une question")
    ap.add_argument("question")
    ap.add_argument("--plan", help="fichier JSON : un plan de routage T1, ou une liste de plans")
    ap.add_argument("--plan-index", type=int, default=0, help="indice du plan si --plan contient une liste")
    ap.add_argument("--request-id", default="REQ-20261106-0001")
    ap.add_argument("--intent", default="procedure")
    ap.add_argument("--agents", nargs="+", default=["procedure"])
    ap.add_argument("--language", default="fr")
    ap.add_argument("--top-k", type=int, default=4)
    ap.add_argument("--mock", action="store_true", help="faux search() et faux LLM (aucun modèle, aucun réseau)")
    ap.add_argument("--merge", action="store_true", help="fusionner les brouillons en un seul")
    ap.add_argument("--show-prompt", action="store_true", help="afficher les prompts envoyés au LLM (stderr)")
    args = ap.parse_args(argv)

    if args.plan:
        with open(args.plan, encoding="utf-8") as handle:
            plan = json.load(handle)
        if isinstance(plan, list):
            plan = plan[args.plan_index]
        plan = plan.get("routing_plan", plan)  # accepte un exemple {question, routing_plan}
    else:
        plan = {"request_id": args.request_id, "intent": args.intent, "domain": "public_services",
                "subdomain": "national_identity_card", "agents": args.agents, "needs_clarification": False}

    search_fn = llm_fn = None
    if args.mock:
        from .mocks import FakeLLM, fake_search
        search_fn, llm_fn = fake_search, FakeLLM()
    if args.show_prompt:
        from .llm import llm_generate
        inner = llm_fn or llm_generate

        def llm_fn(prompt, _inner=inner):  # noqa: F811
            print("----- PROMPT -----\n" + prompt + "\n------------------", file=sys.stderr)
            return _inner(prompt)

    try:
        drafts = run_agents(args.question, plan, language=args.language, search_fn=search_fn,
                            llm_fn=llm_fn, top_k=args.top_k)
        result = merge_drafts(drafts) if args.merge and drafts else drafts
    except AgentError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1

    for draft in ([result] if isinstance(result, dict) else result):
        for error in validate_draft(draft):
            print(f"ATTENTION contrat : {error}", file=sys.stderr)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

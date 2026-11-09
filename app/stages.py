"""Les trois portes vers les tâches des autres membres.

Par défaut on utilise les mocks. Pour brancher la vraie tâche, on définit une
variable d'environnement au format "module:fonction", sans toucher au code :

    export T1_IMPL="backend.orchestrator:route_question"
    export T2_IMPL="backend.agents:run_agents"
    export T3_IMPL="backend.guardrails:validate_answer"

(les chemins ci-dessus sont des EXEMPLES : à remplacer par ceux de vos collègues)
"""
import importlib
import os

from . import mocks


def _load(env_name, default):
    spec = os.getenv(env_name, "mock")
    if spec == "mock":
        return default
    module, _, func = spec.partition(":")
    return getattr(importlib.import_module(module), func)


def route_question(payload):  # T1
    return _load("T1_IMPL", mocks.route_question)(payload)


def run_agents(routing, question):  # T2
    return _load("T2_IMPL", mocks.run_agents)(routing, question)


def validate_answer(agent_output, question):  # T3
    return _load("T3_IMPL", mocks.validate_answer)(agent_output, question)

# Phase 3 - T4 : API, Audit et Interface

## Installation
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt

## Lancer (deux terminaux, depuis la racine du projet)
    uvicorn app.main:app --reload            # API sur http://127.0.0.1:8000  (docs : /docs)
    streamlit run ui/streamlit_app.py        # interface

## Tester
    python -m pytest -q

## Brancher les vraies tâches (format module:fonction, sans modifier le code)
    export T1_IMPL="votre.module:route_question"
    export T2_IMPL="votre.module:run_agents"
    export T3_IMPL="votre.module:validate_answer"
Sans ces variables, les faux T1/T2/T3 (app/mocks.py) sont utilisés.

## Essai rapide
    curl -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" \
         -d '{"question": "Quelles sont les pièces pour la CNI ?"}'

Détails complets : RAPPORT_P3_T4.md

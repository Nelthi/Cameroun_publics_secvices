# T4 — Vectorisation et Indexation (FAISS)

Projet Cameroun Public Service AI · Équipe HEMLE

## Installation (déjà faite sur votre machine)
    python3 -m venv .venv && source .venv/bin/activate
    pip install torch --index-url https://download.pytorch.org/whl/cpu
    pip install -r requirements.txt

## Utilisation (depuis la racine du projet)
    python -m backend.rag.build_index          # construit data/indexes/faiss.index + chunk_mapping.json
    python search_demo.py "Quelles sont les pièces pour la CNI ?" -k 4
    python -m pytest -q                        # tests rapides (faux embedder)
    RUN_SLOW=1 python -m pytest -q             # + test avec le vrai modèle

## Dans le code des agents (Phase 3)
    from backend.rag import search
    resultats = search("ma question", top_k=4)

Détails complets : voir RAPPORT_T4.md

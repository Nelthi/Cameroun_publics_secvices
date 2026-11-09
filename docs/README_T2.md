# T2 — Agents spécialisés (Phase 3)

Projet Cameroun Public Service AI · Équipe HEMLE · Hackathon ITU AI for Good 2026

Ce paquet ajoute la tâche **T2 de la Phase 3** au projet fusionné. Aucun fichier existant n'est
modifié et aucune dépendance n'est ajoutée (`httpx` figure déjà dans `requirements.txt`).

## Installation dans le projet

Depuis le dossier décompressé, copier les dossiers dans la racine du projet fusionné
(celle qui contient `backend/`, `chunking/`, `tests/`) :

```bash
cp -r backend tests examples RAPPORT_T2.md README_T2.md llm.env.example /chemin/vers/Cameroun_publics_secvices/
cd /chemin/vers/Cameroun_publics_secvices
source .venv/bin/activate
```

Nouveaux fichiers : `backend/agents/`, `tests/agents/`, `examples/t2/`.

## Vérifier (sans modèle, sans réseau, sans clé API)

```bash
python -m pytest tests/agents          # attendu : 85 passed (les 3 tests branchés sur FAISS sont ignorés si faiss-cpu est absent)
python -m backend.agents.cli "Quels documents pour ma première CNI ?" --mock
python -m backend.agents.cli "Quels textes et quelles pièces ?" --mock --agents procedure juridique --merge
python -m backend.agents.cli "Bonjour" --mock --intent accueil --agents accueil
```

## Utiliser dans le code (T4 appellera ceci)

```python
from backend.agents import run_agents, merge_drafts

drafts = run_agents(question, routing_plan, language="fr")   # 1 à 3 brouillons (un par agent)
draft = merge_drafts(drafts)                                  # 1 brouillon -> à passer à T3
```

`routing_plan` est exactement la sortie de T1 ; `question` et `language` viennent de la requête T4
(le plan de T1 ne contient pas le texte de la question).

## Avec les vraies dépendances de la Phase 2

1. Reconstruire l'index : `python -m backend.rag.build_index` (l'index d'exemple du dépôt est en 384
   dimensions, le modèle configuré `BAAI/bge-m3` en 1024).
2. Configurer le LLM : voir `llm.env.example`.
3. `python -m backend.agents.cli "Combien coûte la CNI ?" --agents procedure --show-prompt`

Documentation complète : `RAPPORT_T2.md`.

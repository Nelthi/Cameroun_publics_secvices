# Notes de fusion (chef de projet)

Branches fusionnées : champy (T1), nelson (T2 uniquement), alex (T3, repush), didier (T4).
Le code de chaque membre est conservé tel quel ; les seuls changements sont listés ci-dessous.

1. **Nelson : seule la tâche T2 est conservée** (`backend/knowledge_base/processors/`).
   Ses modules T1 (`collectors`), T3 (`chunkers`), T4 (`embeddings`, `vector_store`), `retrieval` et `rag`
   sont retirés de `main`. Ils restent consultables sur la branche locale `nelson-t3-t4`.
2. `processors/processor.py` : une seule ligne modifiée (import). T2 lit maintenant le registre de T1
   via le nouveau fichier `processors/t1_registry.py` (T2 lisait avant le registre de son propre collector).
3. `tests/knowledge_base/t2/test_document_processor.py` (ex `tests/Knowledge_base`, renommé pour éviter un conflit de casse) :
   fixture adaptée au collector de T1 (champ `date`, chemin `data/raw/...`). Les autres tests de Nelson (T1/T3/T4) sont retirés avec leurs modules.
4. `README.md` et `requirements.txt` fusionnés. README d'Alex conservé dans `chunking/README.md`.
   `.env.example` (config RAG de Nelson) retiré.
5. `.pyc` et sous-module vide `t3_chunking` retirés du suivi Git.
6. Nouveau `backend/pipeline/` : relie T1 -> T2 -> T3 -> T4 (sortie T2 `content.segments` -> entrée T3 `pages[]`).
   `python -m backend.pipeline.run fichier.pdf --title ... --institution ... --date 2026-11-04 --domain ... --subdomain ...`
7. Nouveau `backend/pipeline/t2_to_t3.py` : commande de liaison T2 -> T3 (`python -m backend.pipeline.t2_to_t3 DOC-ID`), utilisée aussi par `run.py`.
8. Nouveau `tests/test_pipeline_integration.py` et `README_LANCEMENT.md` (scénario de démonstration et grille de responsabilités).

À faire côté T4 : `data/indexes/faiss.index` (exemple) est en 384 dimensions, le modèle configuré est BAAI/bge-m3 (1024) :
reconstruire avec `python -m backend.rag.build_index`.

## Phase 3

Livrables fusionnés (code des membres inchangé) :
- T1 `backend/orchestration/` + `tests/orchestration/` + docs ; T2 `backend/agents/` + `tests/agents/` + `examples/t2/` + `llm.env.example` ;
  T3 `guardrails/` (README dans le dossier, exemples dans `examples/t3/` au lieu de `examples/`) ; T4 `app/`, `ui/`, `tests/test_t4_api.py`.
- Rapports et README des membres : `docs/` (`README_T2.md`, `RAPPORT_T2.md`, `README_P3_T4.md`, `RAPPORT_P3_T4.md`, docs de T1).
- Le dossier `phase_3/` de T1 contenait aussi une copie du squelette de la Partie 2 : non repris (identique à la fusion, sauf `processors/__init__.py`, où la version de la Partie 2 est conservée).

Ajouts de la fusion :
- `backend/pipeline/phase3.py` : adaptateurs vers les signatures de `app/stages.py` (T2 renvoie une liste de brouillons, fusionnée par son `merge_drafts` ; T3 reçoit les passages depuis `retrieval.passages`) + mode démonstration sans LLM (`PHASE3_LLM=demo`).
- `backend/pipeline/serve.py` : lance l'API de T4 branchée sur les vraies tâches.
- `tests/test_phase3_integration.py` : API -> T1 -> T2 -> T3 -> audit, sur le vrai document de la Partie 2.
- `requirements.txt` (streamlit, requests, pydantic) et `.gitignore` (`data/audit.db`, `data/validated/`).


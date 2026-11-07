# Notes de fusion (chef de projet)

Branches fusionnées : champy (T1), nelson (T2), alex (T3, repush), didier (T4).
Le code de chaque membre est conservé tel quel ; les seuls changements sont listés ci-dessous.

1. `backend/knowledge_base/collectors/` = T1 (champy), nom conforme au guide.
   Nelson (T2) avait écrit un second module « collectors » (ingestion = travail de T1).
   Déplacé sans modification de logique vers `collectors_t2/` ; imports corrigés dans
   `processors/processor.py` et dans ses tests.
2. `tests/Knowledge_base` (Nelson) -> `tests/knowledge_base/t2` (conflit de casse avec le dossier de T1).
3. `README.md` et `requirements.txt` fusionnés (union des dépendances). README d'Alex conservé dans `chunking/README.md`.
4. Fichiers `.pyc` et sous-module vide `t3_chunking` retirés du suivi Git.
5. Ajout de `backend/pipeline/` (nouveau) : relie T1 -> T2 -> T3 -> T4, car les formats ne se branchaient pas
   directement (SQLite différents, sortie T2 en `content.segments` au lieu de `pages`).
   Lancer : `python -m backend.pipeline.run fichier.pdf --title ... --institution ... --date 2026-11-04 --domain ... --subdomain ...`
6. Ajout de `tests/test_pipeline_integration.py`.

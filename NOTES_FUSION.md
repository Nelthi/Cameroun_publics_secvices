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
7. Nouveau `tests/test_pipeline_integration.py`.

À faire côté T4 : `data/indexes/faiss.index` (exemple) est en 384 dimensions, le modèle configuré est BAAI/bge-m3 (1024) :
reconstruire avec `python -m backend.rag.build_index`.

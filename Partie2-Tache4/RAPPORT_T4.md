# Rapport technique — Tâche T4 : Vectorisation et Indexation (cœur du RAG)

**Projet :** Cameroun Public Service AI — Hackathon ITU AI for Good 2026 — Équipe HEMLE

---

## 1. Rôle de la tâche T4

T4 est la dernière étape de la Knowledge Base. Elle prend les **fragments de texte** produits par T3 et construit un **moteur de recherche par le sens** : on pose une question en français, on récupère les fragments de documents officiels qui en parlent le mieux, avec leur document d'origine et leur page.

Ce module ne génère aucune réponse. Il retrouve seulement des passages. C'est l'agent de la Phase 3 qui rédigera la réponse à partir de ces passages.

```
T3 : data/chunks/*.json  ──►  T4 : vectorisation + index  ──►  data/indexes/faiss.index
                                                              data/indexes/chunk_mapping.json
                                                                        │
                                          Agents (Phase 3) ──► search(question, top_k) ◄┘
```

## 2. Le contrat

### Entrée (produite par T3) — `data/chunks/{document_id}.json`
```json
{
  "document_id": "DOC-A1B2C3D4",
  "chunks": [
    {"chunk_id": "DOC-A1B2C3D4-C001", "text": "...", "source_page": 1, "position": 0}
  ]
}
```
Champs obligatoires pour T4 : `document_id`, et pour chaque fragment `chunk_id`, `text`, `source_page`.

### Sortie
1. `data/indexes/faiss.index` : l'index vectoriel (binaire).
2. `data/indexes/chunk_mapping.json` : la table de correspondance.
```json
{ "0": {"chunk_id": "DOC-A1B2C3D4-C001", "document_id": "DOC-A1B2C3D4", "text": "...", "source_page": 1} }
```
3. La fonction `search(query, top_k=4)`, qui renvoie une liste de résultats :
```json
{"rank": 1, "score": 0.71, "distance": 0.58, "chunk_id": "...", "document_id": "...", "text": "...", "source_page": 1}
```

## 3. Comment ça marche (principe)

**Embedding.** Un modèle (`all-MiniLM-L6-v2`) transforme un texte en une liste de 384 nombres, un *vecteur*. Des textes qui parlent de la même chose donnent des vecteurs proches. C'est du calcul mathématique, il n'y a pas de LLM ni de clé API, et ça tourne sur CPU.

**Index FAISS.** FAISS est une bibliothèque qui stocke beaucoup de vecteurs et trouve rapidement les plus proches d'un vecteur donné. Nous utilisons `IndexFlatL2` : recherche **exacte** avec la distance euclidienne. Pour quelques milliers de fragments, c'est instantané.

**Le mapping.** FAISS ne garde que des nombres. Il ne sait dire que « le vecteur n°7 est le plus proche ». Le fichier `chunk_mapping.json` fait le lien entre la position 7 et le texte, le document et la page d'origine. C'est ce qui permet la **traçabilité** demandée par le jury : chaque réponse peut citer sa source.

**Normalisation.** Les vecteurs sont normalisés (longueur 1). Pour des vecteurs normalisés, distance L2² = 2 − 2×cosinus. Le classement par distance est donc identique à un classement par similarité cosinus, et on en déduit un `score` entre 0 et 1 : `score = 1 − distance/2`. Plus le score est haut, plus le fragment est pertinent.

## 4. Structure du projet

```
t4_vectorisation/
├── backend/
│   ├── __init__.py
│   └── rag/
│       ├── __init__.py        # expose search() pour les agents
│       ├── config.py          # chemins, nom du modèle, dimension, top_k par défaut
│       ├── chunk_loader.py    # lit et valide les JSON de T3
│       ├── embedder.py        # texte -> vecteurs (sentence-transformers)
│       ├── vector_store.py    # construire / sauver / charger / interroger l'index
│       └── build_index.py     # script : construit l'index depuis data/chunks/
├── data/
│   ├── chunks/                # ENTRÉE : chunks_exemple*.json (faux fragments de test)
│   └── indexes/               # SORTIE : faiss.index + chunk_mapping.json
├── tests/test_t4.py           # 10 tests (9 rapides + 1 avec le vrai modèle)
├── search_demo.py             # test manuel en ligne de commande
├── pytest.ini · requirements.txt · README.md · RAPPORT_T4.md
```

## 5. Explication module par module

### `config.py`
Un seul endroit pour tous les réglages : dossiers (`CHUNKS_DIR`, `INDEX_DIR`), fichiers de sortie, nom du modèle, dimension (384), `DEFAULT_TOP_K` (4). `BASE_DIR` est calculé à partir de l'emplacement du fichier, donc le projet fonctionne quel que soit le dossier où il est copié.

### `chunk_loader.py`
`load_chunks(dossier)` lit tous les `*.json`, vérifie leur format et renvoie une **liste plate** de fragments `{chunk_id, document_id, text, source_page}`.
- Un fichier invalide ou un champ manquant provoque une erreur claire (nom du fichier + champ concerné). Cela aide à repérer vite une erreur côté T3.
- Les fragments au texte vide sont ignorés (un vecteur de texte vide n'a pas de sens).
- Les `chunk_id` en double sont ignorés, pour pouvoir reconstruire l'index sans doublons.

### `embedder.py`
Classe `Embedder`. Le modèle n'est chargé qu'au premier appel (chargement paresseux), donc importer le module est instantané. `encode(textes)` renvoie un tableau numpy `float32` de forme `(n, 384)`, le type exigé par FAISS.

### `vector_store.py`
- `build_index(chunks, embedder)` : vectorise tous les textes, crée `IndexFlatL2(384)`, y ajoute les vecteurs, construit le mapping `{"0": fragment, "1": fragment, ...}`. L'ordre du mapping est celui d'ajout dans l'index, c'est ce qui fait le lien.
- `save_index` / `load_index` : écrivent et relisent les deux fichiers. `load_index` vérifie que l'index et le mapping ont le même nombre d'éléments, sinon il demande de reconstruire (cela évite de renvoyer le mauvais texte).
- `VectorStore.search(query, top_k)` : refuse une question vide ou un `top_k < 1`; vectorise la question avec **le même modèle** que les fragments; interroge FAISS; ignore les identifiants `-1` (FAISS en renvoie quand il y a moins de résultats que demandé); retrouve chaque fragment dans le mapping. Si `top_k` dépasse le nombre de fragments, on renvoie tout ce qui existe.

### `__init__.py`
Expose `search(query, top_k=4)`. L'index est chargé **une seule fois** en mémoire au premier appel. `reset_store()` force le rechargement après une reconstruction.

### `build_index.py`
Script de construction : charge les fragments, vectorise, sauvegarde, affiche un résumé. Les chemins peuvent être changés par arguments (`--chunks-dir`, `--index-path`, `--mapping-path`).

## 6. Utilisation

```bash
source .venv/bin/activate
python -m backend.rag.build_index
python search_demo.py "Quelles sont les pièces pour la CNI ?" -k 4
```
Dans le code des agents :
```python
from backend.rag import search
for r in search("pièces pour la CNI", top_k=4):
    print(r["score"], r["document_id"], r["source_page"], r["text"])
```

**Important :** à chaque fois que T3 livre de nouveaux fragments, relancer `python -m backend.rag.build_index`. L'index n'est pas mis à jour automatiquement.

## 7. Tests

`python -m pytest -q` lance 9 tests rapides, qui utilisent un **faux embedder** (sac de mots haché en 384 dimensions) pour ne pas télécharger le modèle. Ils vérifient le **contrat** :
- le loader lit les exemples, refuse un champ manquant, ignore vides et doublons;
- l'index a 384 dimensions et autant de vecteurs que de fragments, le mapping a les bonnes clés;
- sauvegarde puis rechargement donnent le même résultat;
- la recherche renvoie le bon fragment en premier, gère `top_k` trop grand, refuse une entrée invalide;
- le chargement d'un index absent donne un message utile.

Un 10e test (`RUN_SLOW=1 python -m pytest -q`) utilise le vrai modèle. Résultat de ma dernière exécution des tests rapides : **9 réussis, 1 ignoré** (le test lent). Je n'ai pas pu lancer le vrai modèle dans mon environnement : lancez-le chez vous pour confirmer.

Les fichiers `chunks_exemple*.json` sont des **faux fragments** marqués `[EXEMPLE FICTIF]`. Ils ne reflètent pas de vraies procédures. Supprimez-les de `data/chunks/` quand T3 livre les vrais fichiers, sinon ils seront indexés avec les vrais.

## 8. Limites et améliorations possibles

| Limite | Piste |
|---|---|
| Reconstruction complète à chaque fois | Ajouter un mode incrémental (`index.add` sur les nouveaux fragments seulement) |
| `all-MiniLM-L6-v2` est surtout entraîné sur l'anglais | Tester `paraphrase-multilingual-MiniLM-L12-v2` (changer `MODEL_NAME` et `EMBEDDING_DIM`, reconstruire) |
| `IndexFlatL2` compare avec tous les vecteurs | Très bien jusqu'à quelques dizaines de milliers de fragments; au-delà, passer à `IndexIVFFlat` ou `IndexHNSWFlat` |
| Pas de filtre par domaine ou institution | Ajouter ces champs dans le mapping et filtrer après la recherche |
| Pas de seuil de pertinence | Les agents peuvent ignorer les résultats sous un `score` minimal pour éviter de répondre avec des passages hors sujet (utile pour la détection des lacunes) |

## 9. Points d'attention pour l'équipe

1. **Même modèle partout.** Questions et fragments doivent être vectorisés avec le même modèle, sinon la recherche donne des résultats faux. Si on change de modèle, on reconstruit l'index.
2. **Le format de T3 est le contrat.** Si T3 renomme un champ (`source_page`, `chunk_id`, `text`), `load_chunks` refusera le fichier avec un message explicite.
3. **Index et mapping vont ensemble.** Il ne faut jamais en modifier ou en copier un sans l'autre.

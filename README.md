# Cameroun Public Service AI

Projet ITU AI for Good 2026 — équipe HEMLE.

Assistant d’accès aux informations des services publics camerounais, à partir
d’une base de connaissances documentaire (pipeline RAG préparé en plusieurs
modules).

## Objectif (Phase 2 — Knowledge Base)

Pipeline modulaire :

1. **T1 — Ingestion and Storage** : importer et enregistrer les documents
2. **T2 — Extraction and Cleaning** : extraire et nettoyer le texte
3. **T3 — Chunking** : découper en segments
4. **T4 — Vectorization and FAISS** : embeddings + recherche sémantique

État actuel : **T1 complet** (cœur + API FastAPI + suite pytest).

## Prérequis

- Ubuntu
- Python 3.12+

## Installation

```bash
cd Cameroun_publics_secvices
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Structure

```text
backend/knowledge_base/
  collectors/    # T1 — ingestion
  processors/    # T2 — extraction
  chunkers/      # T3 — chunking
  vectorizers/   # T4 — embeddings / FAISS
  retrieval/     # recherche sémantique
  database/      # SQLite
  api/           # FastAPI + Swagger

data/
  raw/           # originaux importés (T1)
  processed/     # textes extraits (T2)
  chunks/        # segments (T3)
  indexes/       # index FAISS (T4)
  metadata/      # base SQLite

tests/knowledge_base/
docs/
01_CNI/          # documents sources métier (hors pipeline data/)
```

## T1 — Ingestion and Storage

- Formats : PDF, DOCX, TXT
- Vérification d’extension et de signature (`%PDF`, DOCX ZIP + `word/document.xml`)
- Empreinte SHA-256 ; doublon → pas de nouvelle copie, retour de l’ID existant
- Stockage : `data/raw/{domain}/{subdomain}/{document_id}.{ext}`
- Registre SQLite : `data/metadata/documents.sqlite3`
- Route : `POST /documents/upload`

T1 **n’extrait pas** le contenu des documents.

### Démarrer l’API

```bash
source .venv/bin/activate
uvicorn backend.knowledge_base.api.app:app --reload --host 127.0.0.1 --port 8000
```

### Documentation Swagger

- Swagger UI : http://127.0.0.1:8000/docs
- ReDoc : http://127.0.0.1:8000/redoc
- Schéma OpenAPI : http://127.0.0.1:8000/openapi.json

### Exemple `curl`

```bash
curl -X POST "http://127.0.0.1:8000/documents/upload" \
  -F "file=@01_CNI/Plaquette-20-Mai-2025-FR-ok.pdf" \
  -F "title=Plaquette CNI" \
  -F "institution=DGSN" \
  -F "date=2025-05-20" \
  -F "domain=public_services" \
  -F "subdomain=national_identity_card"
```

Réponse attendue (contrat Phase 2) :

```json
{
  "document_id": "DOC-A1B2C3D4",
  "sha256": "9f2c...",
  "original_filename": "Plaquette-20-Mai-2025-FR-ok.pdf",
  "stored_path": "data/raw/public_services/national_identity_card/DOC-A1B2C3D4.pdf",
  "upload_date": "2026-11-04T10:00:00",
  "domain": "public_services",
  "institution": "DGSN",
  "status": "stored"
}
```

Codes HTTP :

- `201` : nouveau document stocké
- `200` : doublon (`is_duplicate: true`)
- `400` : fichier ou métadonnées invalides
- `415` : format non supporté

### Exemple Python (sans API)

```python
from backend.knowledge_base.collectors import DocumentCollector, DocumentMetadata

collector = DocumentCollector(data_root="data")
result = collector.import_document(
    "01_CNI/Plaquette-20-Mai-2025-FR-ok.pdf",
    DocumentMetadata(
        title="Plaquette CNI",
        institution="DGSN",
        date="2025-05-20",
        domain="public_services",
        subdomain="national_identity_card",
    ),
)
print(result.to_dict())
```

## Tests T1

La suite couvre : **OK / invalide / vide / doublon / métadonnées** (cœur, SQLite, API).

```bash
source .venv/bin/activate

# Toute la suite T1
python -m pytest tests/knowledge_base/test_collectors -v

# Par fichier
python -m pytest tests/knowledge_base/test_collectors/test_document_collector.py -v
python -m pytest tests/knowledge_base/test_collectors/test_repository.py -v
python -m pytest tests/knowledge_base/test_collectors/test_documents_api.py -v
```

## Documents sources

Les PDF du dossier `01_CNI/` sont des documents de référence. Ils ne sont pas
modifiés par le pipeline ; T1 les copiera vers `data/raw/` lors de l’import.

## T4 — Vectorisation et Indexation (FAISS)

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

## T2 (branche nelson) — Embedding Generator

Le module `backend.knowledge_base.embeddings` transforme les chunks produits par le
Text Chunker en vecteurs numériques avec Sentence Transformers.

### Modèle par défaut

`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` : modèle multilingue
adapté notamment au français. Le modèle est téléchargé automatiquement au premier
lancement, puis réutilisé depuis le cache local. La génération se fait localement.

### Installation

```bash
python -m pip install -r requirements.txt
```

### Générer les embeddings d'un document

```bash
python -m backend.knowledge_base.embeddings.cli DOC-XXXXXXXXXXXX
```

### Générer les embeddings de tous les documents chunkés

```bash
python -m backend.knowledge_base.embeddings.cli --all
```

Options disponibles :

- `--model` : choisir un autre modèle Sentence Transformers.
- `--batch-size` : nombre de chunks encodés par lot (défaut : 32).
- `--device cpu|cuda|mps` : choisir le matériel de calcul ; par défaut, détection automatique.
- `--domain` : limiter `--all` à un domaine.
- `--data-root` : changer le dossier de données.

### Fichiers produits

Pour chaque document, le module crée :

```text
data/embeddings/<domain>/<subdomain>/<document_id>/
├── vectors.npy       # matrice float32 : un vecteur par chunk
└── metadata.json     # correspondance vecteur <-> chunk et provenance
```

Les vecteurs sont normalisés en norme L2. Ils pourront donc être comparés par
produit scalaire dans FAISS (`IndexFlatIP`) pour approximer la similarité cosinus.
Le fichier `metadata.json` conserve les identifiants des chunks, leur texte, leurs
pages et les métadonnées du document source.

### Tests

Les tests utilisent un encodeur factice déterministe : ils vérifient le pipeline
sans télécharger le modèle d'IA.

```bash
python -m pytest tests/knowledge_base -v
```

## Vector Store (FAISS)

Le module `backend.knowledge_base.vector_store` construit un index global à partir
des fichiers `data/embeddings/**/vectors.npy` et de leurs manifestes `metadata.json`.
Il utilise `faiss.IndexFlatIP`. Les vecteurs doivent être normalisés en norme L2 :
le produit scalaire représente alors la similarité cosinus.

### Dépendance

```bash
python -m pip install -r requirements.txt
```

La dépendance `faiss-cpu` permet d'utiliser FAISS sur le processeur. Le module
n'utilise pas de GPU pour l'index FAISS.

### Construire ou reconstruire l'index

Après avoir généré les embeddings des documents :

```bash
python -m backend.knowledge_base.vector_store.cli --build
```

### Rechercher des passages

```bash
python -m backend.knowledge_base.vector_store.cli --search "Quels documents fournir pour une première CNI ?" --top-k 5
```

La question est vectorisée avec le même modèle Sentence Transformers que celui
utilisé pour les documents. Le résultat contient le score de similarité, le texte,
l'identifiant du document, l'identifiant du chunk, la page et les métadonnées de
provenance.

### Fichiers produits

```text
data/vector_store/
├── index.faiss       # index vectoriel FAISS
└── metadata.json     # correspondance entre les positions FAISS et les chunks
```

L'index est reconstruit depuis `data/embeddings` à chaque commande `--build`.
Tous les embeddings d'un même index doivent provenir du même modèle et avoir la
même dimension. Après ajout ou modification d'embeddings, reconstruisez l'index.

### Tests

```bash
python -m pytest tests/knowledge_base -v
```

Les tests du Vector Store utilisent un FAISS simulé afin de tester la logique sans
installation de FAISS ni téléchargement du modèle. En environnement réel, installez
bien `faiss-cpu` depuis `requirements.txt`.

## Retrieval Engine

Le module `backend.knowledge_base.retrieval` orchestre la récupération de passages
à partir du Vector Store FAISS. Il vectorise la question via le même encodeur que
celui du Vector Store, récupère une liste élargie de candidats, applique les filtres
métier puis prépare un contexte textuel avec les références de provenance.

### Rechercher des passages

```bash
python -m backend.knowledge_base.retrieval.cli "Quels documents fournir pour une première CNI ?" --top-k 5
```

### Filtrer par domaine et sous-domaine

```bash
python -m backend.knowledge_base.retrieval.cli \
  "Quels documents fournir pour une première CNI ?" \
  --domain public_services \
  --subdomain national_identity_card \
  --top-k 5
```

Options principales :

- `--top-k` : nombre maximal de chunks retournés (défaut : 5).
- `--candidate-k` : nombre de candidats recherchés dans FAISS avant filtrage (défaut : 50).
- `--domain` et `--subdomain` : filtres insensibles à la casse.
- `--min-score` : seuil optionnel de similarité cosinus. Aucun seuil n'est imposé par défaut ; il devra être calibré avec un jeu de questions de test représentatif.
- `--context-char-limit` : taille maximale du contexte préparé (défaut : 12 000 caractères).
- `--include-inactive` : inclure explicitement les documents dont le statut est différent de `active`.
- `--data-root`, `--model` et `--device` : paramètres transmis au Vector Store.

Le moteur renvoie les chunks avec leur score, leur document source, leur identifiant,
leur page et leurs métadonnées. Le champ `context` rassemble les passages et leurs
références pour l'étape RAG. Le Retrieval Engine ne génère pas encore de réponse avec
un LLM : il fournit uniquement les éléments documentaires à citer.

Le filtrage intervient après la recherche FAISS. `candidate-k` doit donc être assez
grand pour fournir suffisamment de résultats après filtrage ; augmentez-le si un
filtre strict retourne trop peu de passages. Les scores dépendent du modèle et du
corpus : ne les interprétez pas comme des probabilités de vérité.

### Tests

```bash
python -m pytest tests/knowledge_base -v
```

Les tests du Retrieval Engine utilisent un Vector Store factice afin de tester les
filtres, le classement, le seuil et la préparation du contexte sans charger FAISS ni
le modèle d'embedding.

## RAG Pipeline

Le module `backend.knowledge_base.rag` relie le Retrieval Engine à un LLM. Il récupère
les passages, construit un prompt avec des références `[S1]`, `[S2]`, puis demande
au modèle de répondre uniquement à partir des extraits. Si aucun passage n'est
retrouvé, le pipeline s'abstient et ne contacte pas le LLM.

### Configuration du fournisseur LLM

Le client fourni utilise une API compatible avec `/v1/chat/completions`. Il peut
s'agir d'un fournisseur distant ou d'un serveur local compatible. Configurez les
variables d'environnement suivantes dans le terminal :

```bash
export RAG_API_BASE_URL="https://votre-fournisseur.example/v1"
export RAG_API_KEY="votre-cle-api"
export RAG_MODEL="nom-du-modele-chat"
```

`RAG_API_KEY` peut être omise pour un serveur local qui n'exige pas de clé. Ne
commitez jamais une vraie clé API dans GitHub. La génération nécessite un modèle
LLM configuré ; le modèle d'embedding MiniLM n'est pas un modèle conversationnel.

### Poser une question

Après avoir généré les embeddings et construit l'index FAISS :

```bash
python -m backend.knowledge_base.rag.cli \
  "Quels documents fournir pour une première CNI ?" \
  --domain public_services \
  --subdomain national_identity_card \
  --top-k 5
```

Le résultat JSON contient la question, la réponse, l'indication d'abstention,
le modèle utilisé et les références documentaires (identifiant, chunk, page,
institution et URL lorsqu'elles existent).

### Sécurité et limites

- Le pipeline ne répond pas à partir du LLM lorsqu'aucun passage n'est retrouvé.
- Le prompt traite les extraits documentaires comme des données, pas comme des
  instructions, afin de réduire les risques d'injection de prompt provenant d'un document.
- Les références retournées correspondent aux extraits transmis au modèle ; cela
  ne constitue pas une vérification automatique de chaque affirmation. Il faudra
  ajouter des tests de fidélité et une validation humaine des réponses sensibles.
- Le seuil de similarité doit être calibré sur des questions/réponses de référence.
- La disponibilité, la confidentialité et les conditions de conservation des données
  dépendent du fournisseur LLM choisi. Évitez d'envoyer des données personnelles
  de citoyens dans ce prototype.

### Tests

```bash
python -m pytest tests/knowledge_base -v
```

Les tests du RAG utilisent un Retriever et un LLM factices : ils vérifient le flux,
les références et l'abstention sans appel réseau ni clé API.

## T3 — Découpage (Chunking)

Module `chunking/` à la racine du projet (code d'Alex, voir `chunking/README.md` pour le détail du contrat).
Depuis la racine du projet :

```bash
python -m chunking examples/input_t2_example.json --out-dir data/chunks
python -m chunking.validate data/chunks/<document_id>.json
```

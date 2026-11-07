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

## T2 — Extraction et nettoyage

Module `backend/knowledge_base/processors/` (code de Nelson). Lit le registre SQLite de T1,
extrait le texte (PDF avec pypdf page par page, DOCX avec python-docx tableaux compris, TXT UTF-8),
le nettoie, et écrit `data/processed/{domain}/{subdomain}/{document_id}.json`
(`content.segments` avec `page_number`, `processing.warnings`, statut `needs_ocr_or_review` pour un PDF scanné).

```bash
python -m backend.knowledge_base.processors.cli DOC-XXXXXXXX
python -m backend.knowledge_base.processors.cli --all
```

## T3 — Découpage (Chunking)

Module `chunking/` à la racine du projet (code d'Alex, voir `chunking/README.md` pour le détail du contrat).
Depuis la racine du projet :

```bash
python -m chunking examples/input_t2_example.json --out-dir data/chunks
python -m chunking.validate data/chunks/<document_id>.json
```

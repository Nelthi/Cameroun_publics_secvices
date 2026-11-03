# Knowledge Base — Document Collector, Processor et Text Chunker

Ce projet contient les trois premières étapes du pipeline de construction de la base documentaire :

1. **Document Collector** : importe les PDF, DOCX et TXT, conserve les originaux dans `data/raw/` et enregistre les métadonnées dans SQLite.
2. **Document Processor** : extrait et normalise le texte, puis écrit un JSON dans `data/processed/`.
3. **Text Chunker** : découpe les segments normalisés en blocs de texte (chunks) et écrit un JSON dans `data/chunks/`.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Tests

```bash
python -m pytest tests/knowledge_base -v
```

## Utilisation du Collector

```python
from backend.knowledge_base.collectors import DocumentCollector, DocumentMetadata

collector = DocumentCollector(data_root="data")
metadata = DocumentMetadata(
    title="Procédure de demande de CNI",
    domain="public_services",
    subdomain="national_identity_card",
    institution="DGSN",
    document_type="procedure",
    language="fr",
)
result = collector.import_document("documents/procedure_cni.pdf", metadata)
print(result.document_id)
```

## Utilisation du Processor

```bash
python -m backend.knowledge_base.processors.cli DOC-XXXXXXXXXXXX
python -m backend.knowledge_base.processors.cli --all
```

## Utilisation du Text Chunker

Le Chunker travaille sur les JSON produits par le Processor. Il conserve l'identifiant du document, les métadonnées, la page PDF (si disponible) et un identifiant unique pour chaque chunk.

```bash
# Un document
python -m backend.knowledge_base.chunkers.cli DOC-XXXXXXXXXXXX

# Tous les documents traités
python -m backend.knowledge_base.chunkers.cli --all

# Paramétrer la taille et le chevauchement (en caractères)
python -m backend.knowledge_base.chunkers.cli DOC-XXXXXXXXXXXX --chunk-size 1000 --overlap 150

# Tous les documents d'un domaine
python -m backend.knowledge_base.chunkers.cli --all --domain public_services
```

Valeurs par défaut : `chunk_size=1000` caractères et `overlap=150` caractères. Le découpage privilégie les frontières de paragraphes et ne mélange pas les segments source. Pour les PDF, cela permet de garder le numéro de page associé à chaque chunk.

Les résultats sont enregistrés dans :

```text
data/
├── raw/          # originaux importés
├── processed/    # texte extrait et normalisé
├── chunks/       # chunks prêts pour les embeddings
└── metadata/     # base SQLite
```

## Limites connues

- Les PDF scannés nécessitent une étape OCR avant de produire des chunks.
- La taille et le chevauchement sont mesurés en caractères, pas en tokens. Ils seront ajustés après le choix du modèle d'embeddings et du modèle de langage.
- Le découpage est conscient des paragraphes, mais ne réalise pas encore une segmentation sémantique avancée (titres, articles de loi, sections).

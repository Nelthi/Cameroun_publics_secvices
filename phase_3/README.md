# Cameroun Public Service AI

Projet ITU AI for Good 2026 — équipe HEMLE.

Assistant d’accès aux informations des services publics camerounais.

## État actuel

| Phase | Module | Statut |
|---|---|---|
| **Phase 2** | T1 Ingestion & Storage (KB) | **Livré** (API + tests) |
| **Phase 2** | T2 / T3 / T4 Knowledge Base | Squelettes / hors scope branche |
| **Phase 3** | T1 Orchestrateur & Routage | **Livré** (`route_question` + doc + tests) |

> Attention : « T1 » désigne deux modules distincts selon la phase.
> Phase 2 T1 = ingestion de documents. Phase 3 T1 = routage de questions.

Doc détaillée Phase 3 T1 : [`docs/phase3_t1_orchestration.md`](docs/phase3_t1_orchestration.md)  
Source NotebookLM : [`docs/notebooklm_source_hemle_t1.md`](docs/notebooklm_source_hemle_t1.md)

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
backend/
  knowledge_base/          # Phase 2 — Knowledge Base
    collectors/            # Phase 2 T1 — ingestion
    processors/            # Phase 2 T2
    chunkers/              # Phase 2 T3
    vectorizers/           # Phase 2 T4
    database/
    api/
  orchestration/           # Phase 3 T1 — orchestrateur / routage
    models.py
    exceptions.py
    question_cleaner.py
    intent_classifier.py
    domain_classifier.py
    clarification_detector.py
    agent_selector.py
    orchestrator.py        # route_question()
    config.py              # mots-clés configurables

data/
  raw/ processed/ chunks/ indexes/ metadata/

tests/
  knowledge_base/          # tests Phase 2 T1
  orchestration/           # tests Phase 3 T1

docs/
  phase3_t1_orchestration.md
01_CNI/                    # documents sources métier
```

---

## Phase 3 — T1 Orchestrateur et Routage

Objectif : analyser une question citoyenne et produire un **plan de routage**
JSON (sans LLM, règles + mots-clés).

### Progression

| Étape | Composant | Statut |
|---|---|---|
| 0 | Validation entrée + modèles | ✅ |
| 1 | `question_cleaner` | ✅ |
| 2 | `intent_classifier` | ✅ |
| 3 | `domain_classifier` | ✅ |
| 4 | `clarification_detector` | ✅ |
| 5 | `agent_selector` | ✅ |
| 6 | `orchestrator` + `route_question` | ✅ |
| 7 | Doc finale / polish | ✅ |

### Contrat d’entrée (T4 → T1)

```json
{
  "request_id": "REQ-20261106-0001",
  "question": "Comment obtenir une carte nationale d'identité au Cameroun ?",
  "language": "fr",
  "timestamp": "2026-11-06T10:00:00"
}
```

### Contrat de sortie (strict)

```json
{
  "request_id": "REQ-20261106-0001",
  "intent": "procedure",
  "domain": "public_services",
  "subdomain": "national_identity_card",
  "agents": ["procedure"],
  "needs_clarification": false
}
```

### Intentions

`accueil` | `procedure` | `juridique` | `donnees_personnelles` | `hors_sujet`

Priorité multi-intentions :
`donnees_personnelles` > `juridique` > `procedure` > `accueil` > `hors_sujet`

### Agents (indicatifs, à valider avec T2)

- 1 à 3 agents selon l’intention (et intentions secondaires détectées)
- `hors_sujet` → liste vide
- Exemples : `procedure`, `juridique`, `accueil`, `donnees_personnelles`

### Exemple Python — `route_question`

```python
from backend.orchestration import route_question

plan = route_question({
    "request_id": "REQ-20261106-0001",
    "question": "Comment obtenir une carte nationale d'identité au Cameroun ?",
    "language": "fr",
    "timestamp": "2026-11-06T10:00:00",
})
print(plan)
```

T1 Phase 3 n’appelle ni T2, ni T3, ni T4.

### Personnaliser les règles

Éditer `backend/orchestration/config.py` :
- `INTENT_KEYWORDS`
- `DOMAIN_KEYWORDS`
- `VAGUE_QUESTION_PATTERNS`
- `INTENT_TO_AGENTS`

### Tests Phase 3 T1

```bash
source .venv/bin/activate
python -m pytest tests/orchestration -v
```

### Dépannage rapide

| Problème | Piste |
|---|---|
| Timestamp rejeté | Utiliser ISO 8601 (`2026-11-06T10:00:00`) |
| Mauvaise intention | Ajouter/ajuster les mots-clés dans `config.py` |
| Domaine `unknown` | Normal si aucun signal ; sinon enrichir `DOMAIN_KEYWORDS` |

---

## Phase 2 — T1 Ingestion and Storage

- Formats : PDF, DOCX, TXT
- Signature, SHA-256, anti-doublon, stockage `data/raw/...`, SQLite
- Route : `POST /documents/upload`

### Démarrer l’API documents

```bash
source .venv/bin/activate
uvicorn backend.knowledge_base.api.app:app --reload --host 127.0.0.1 --port 8000
```

- Swagger : http://127.0.0.1:8000/docs
- ReDoc : http://127.0.0.1:8000/redoc

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

### Tests Phase 2 T1

```bash
source .venv/bin/activate
python -m pytest tests/knowledge_base/test_collectors -v
```

## Tous les tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

## Documents sources

Les PDF du dossier `01_CNI/` sont des documents de référence. Ils ne sont pas
modifiés par le pipeline ; l’ingestion Phase 2 les copie vers `data/raw/`.

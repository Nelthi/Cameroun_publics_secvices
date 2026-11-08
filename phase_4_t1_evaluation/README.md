# Phase 4 — T1 Jeu de test et Évaluation

Livrable autonome (équipe HEMLE / Champy).  
**Ne pas confondre** avec Phase 2 (ingestion) ni Phase 3 (orchestrateur).

## Objectif

- Gérer 20–30 questions de test manuelles
- Appeler l’API Phase 3 `POST /ask`
- Comparer obtenu vs attendu
- Calculer les métriques
- Produire `eval_report.json` et `eval_report.csv`

## État

| Étape | Contenu | Statut |
|---|---|---|
| 0 | Cadre, dossier, décisions, contrat provisoire | ✅ |
| 1 | Socle modèles / config / validation | ✅ |
| 2 | Jeu `questions.json` | ✅ |
| 3 | Client HTTP `/ask` (+ mock) | ✅ |
| 4 | Comparaison + métriques | ✅ |
| 5 | Rapports JSON/CSV + runner CLI | ✅ |
| 6 | Tests + doc Ubuntu | ✅ |

Doc Ubuntu complète : [`docs/phase4_t1_evaluation.md`](docs/phase4_t1_evaluation.md)  
Cadre étape 0 : [`docs/ETAPE_0_CADRE.md`](docs/ETAPE_0_CADRE.md)

## Structure

```text
phase_4_t1_evaluation/
  evaluation/       # module Python T1 Phase 4
  tests/evaluation/
  data/             # questions.json
  reports/          # eval_report_*.json/csv
  docs/
```

## Installation rapide (Ubuntu / Python 3.12)

```bash
cd Cameroun_publics_secvices
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r phase_4_t1_evaluation/requirements.txt
```

## Configuration (pas de secrets en dur)

```bash
export EVAL_API_BASE_URL="http://127.0.0.1:8000"
export EVAL_HTTP_TIMEOUT_SECONDS="30"
export EVAL_ASK_MODE="mock"   # ou "http" quand /ask est dispo
```

Voir `.env.example`.

## Exécuter l'évaluation

```bash
cd phase_4_t1_evaluation
source ../.venv/bin/activate
export EVAL_ASK_MODE=mock
python -m evaluation.cli --run-id demo001
```

Rapports :
- `reports/eval_report_demo001.json`
- `reports/eval_report_demo001.csv`

Sans `--force`, un `run_id` déjà utilisé est refusé.

## Lancer les tests

```bash
cd phase_4_t1_evaluation
source ../.venv/bin/activate
python -m pytest tests/evaluation -v
```

## Point important pour l’assembleur

Ce dossier est **autonome**. Pour intégrer plus tard dans le monorepo :

- copier `evaluation/` → `evaluation/` (ou `backend/evaluation/` selon convention équipe)
- copier `tests/evaluation/`
- **ne pas** écraser le `requirements.txt` / README de `main`

Voir `LIVRAISON.md`.

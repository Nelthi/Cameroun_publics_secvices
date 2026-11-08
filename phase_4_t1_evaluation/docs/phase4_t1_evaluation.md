# Phase 4 — T1 Jeu de test et Évaluation

Module responsable : **HEMLE / Champy**  
Périmètre : charger un jeu de questions, appeler `POST /ask`, comparer obtenu vs attendu, produire les métriques et rapports.

**Aucun LLM.** Comparaison déterministe sur `document_id` et refus.

Ce module **n’implémente pas** l’API `/ask` (Phase 3). Sans serveur, utiliser `EVAL_ASK_MODE=mock`.

---

## 1. Installation (Ubuntu / Python 3.12)

Depuis la racine du dépôt :

```bash
cd Cameroun_publics_secvices
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r phase_4_t1_evaluation/requirements.txt
```

Dépendances : `httpx`, `pytest`.

## 2. Configuration

Variables d’environnement (aucune URL/secret en dur) :

| Variable | Défaut | Rôle |
|---|---|---|
| `EVAL_ASK_MODE` | `mock` | `mock` ou `http` |
| `EVAL_API_BASE_URL` | `http://127.0.0.1:8000` | Base URL Phase 3 |
| `EVAL_ASK_PATH` | `/ask` | Chemin relatif |
| `EVAL_HTTP_TIMEOUT_SECONDS` | `30` | Timeout HTTP |

Exemple :

```bash
cp phase_4_t1_evaluation/.env.example phase_4_t1_evaluation/.env
# puis exporter ou sourcer les variables
export EVAL_ASK_MODE=mock
```

## 3. Exécuter l’évaluation

```bash
cd phase_4_t1_evaluation
source ../.venv/bin/activate
export EVAL_ASK_MODE=mock
python -m evaluation.cli --run-id demo001
```

Mode HTTP (quand `POST /ask` est disponible) :

```bash
export EVAL_ASK_MODE=http
export EVAL_API_BASE_URL="http://127.0.0.1:8000"
python -m evaluation.cli --run-id http_run_001
```

Options utiles :

```bash
python -m evaluation.cli --questions data/questions.json --reports-dir reports --run-id mon_run
python -m evaluation.cli --run-id mon_run --force   # écrasement explicite seulement
```

## 4. Rapports produits

Fichiers (suffixés par `run_id`, pas d’écrasement silencieux) :

- `reports/eval_report_{run_id}.json`
- `reports/eval_report_{run_id}.csv`

Contrat JSON obligatoire :

```json
{
  "run_id": "demo001",
  "n_questions": 25,
  "metrics": {
    "source_hit_rate": 1.0,
    "correct_refusal_rate": 1.0,
    "avg_duration_ms": 0.1
  },
  "failures": []
}
```

Chaque failure : `question_id`, `expected`, `got`, `request_id`.

## 5. Métriques (dénominateurs)

| Métrique | Numérateur | Dénominateur |
|---|---|---|
| `source_hit_rate` | ≥1 `document_id` attendu retrouvé | questions non-refus avec sources attendues |
| `correct_refusal_rate` | refus attendu **et** obtenu (sans sources) | questions `expected.refused == true` |
| `avg_duration_ms` | somme des `duration_ms` des appels réussis | nombre d’appels réussis |

Une erreur réseau / timeout / HTTP 4xx-5xx / JSON invalide **n’est pas** un refus correct : elle va dans `failures` (`error_type: ask_client_error`).

## 6. Pipeline interne

```text
load_questions_file
  → create_ask_client (mock | http)
  → ask(case) pour chaque question
  → compare_case
  → compute_metrics / build_report
  → write_reports (JSON + CSV)
```

| Fichier | Rôle |
|---|---|
| `config.py` | Env → `EvalConfig` |
| `models.py` | Contrats questions / ask / rapport |
| `questions_loader.py` | Validation `questions.json` |
| `ask_client.py` | Client HTTP + mock |
| `comparator.py` | Source hit + refus |
| `metrics.py` | Agrégation métriques |
| `reporter.py` | Écriture JSON/CSV |
| `runner.py` | Orchestration |
| `cli.py` | Point d’entrée CLI |

## 7. Jeu de questions

Fichier : `data/questions.json` (25 cas fictifs, pas de PII).

Schéma minimal d’une question :

```json
{
  "question_id": "Q001",
  "question": "Comment obtenir une CNI ?",
  "language": "fr",
  "expected": {
    "refused": false,
    "sources": [{"document_id": "DOC-CNI-GUIDE-001"}]
  }
}
```

Règles : ids uniques ; si `refused=true` alors `sources` vide ; pas de champs racine inattendus.

## 8. Tests

```bash
cd phase_4_t1_evaluation
source ../.venv/bin/activate
python -m pytest tests/evaluation -v
```

Couverture : config, modèles, validation questions, dataset 25 cas, client mock/HTTP, timeout/réseau/JSON invalide, comparaison, métriques, rapports, runner, edge cases.

## 9. Dépannage (Ubuntu)

| Symptôme | Cause probable | Action |
|---|---|---|
| `ModuleNotFoundError: evaluation` | mauvais cwd / PYTHONPATH | lancer depuis `phase_4_t1_evaluation/` |
| `EVAL_ASK_MODE doit valoir…` | valeur autre que `http`/`mock` | exporter `mock` ou `http` |
| `AskClientError` Timeout / réseau | API absente ou lente | vérifier serveur `/ask` ou rester en `mock` |
| `AskClientError` champs manquants | contrat `/ask` différent | aligner parseur sur contrat officiel |
| `ReportWriteError` existe déjà | même `run_id` | changer `--run-id` ou `--force` |
| `QuestionsValidationError` | JSON invalide | contrôler schéma (ids, refused, sources) |
| pytest introuvable | venv non activé | `source ../.venv/bin/activate` |

## 10. Point assembleur

Dossier autonome. Pour intégrer au monorepo : copier `evaluation/`, `tests/evaluation/`, `data/` — **ne pas** écraser le `requirements.txt` / README de `main`.

Détail cadre : [`ETAPE_0_CADRE.md`](ETAPE_0_CADRE.md) · Livraison : [`../LIVRAISON.md`](../LIVRAISON.md)

## 11. Décisions ouvertes (équipe)

1. Brancher le contrat officiel `POST /ask` dès livraison Phase 3
2. Seuil d’acceptation des métriques (hors scope T1)
3. Emplacement final dans le monorepo (`evaluation/` vs `backend/evaluation/`)

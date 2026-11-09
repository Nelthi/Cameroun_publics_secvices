# gaps/ — Phase 4, T2 : Analyse des lacunes

Lit les lacunes de l'audit (Phase 3) et les échecs de l'évaluation (T1), les regroupe par sujet,
les classe par fréquence et suggère le document et l'institution à chercher.
Produit `data/reports/gap_report.json`, lu par **T3** (combler les lacunes) et **T4** (page Qualité).

Ce dossier est autonome : il n'importe rien de `backend/` ni de `chunking/`, et n'ajoute aucune
dépendance (`httpx` n'est utilisé que pour `GET /gaps`).

## Essayer tout de suite (faux fichiers, rien à configurer)

```bash
python -m gaps --mock            # affiche le résumé ; le rapport est écrit dans un dossier temporaire
python -m pytest tests/gaps      # 87 tests
```

## Utilisation réelle

```bash
python -m gaps                                   # emplacements par défaut (voir ci-dessous)
python -m gaps --audit-db data/audit.db --eval-report data/reports/eval_report.json \
               --questions data/eval/questions.json
python -m gaps --api-url http://127.0.0.1:8000 --source api      # si audit.db n'est pas lisible
python -m gaps --since 2026-11-13                # après la mise à jour de T3 : ne compter que le nouveau
```

| Option | Rôle | Défaut |
|---|---|---|
| `--audit-db` | base d'audit de la Phase 3 | `data/audit.db`, `data/metadata/audit.db`, `audit.db` |
| `--api-url` / `--source` | `GET /gaps` ; `auto` (audit.db puis API), `audit`, `api` | `auto` |
| `--eval-report` | rapport de T1 | `data/reports/eval_report.json` (facultatif) |
| `--questions` | texte des questions de T1 (par `question_id`) | `data/eval/questions.json` (facultatif) |
| `--out` | rapport produit | `data/reports/gap_report.json` |
| `--since` | date ISO 8601 : ignore les lacunes d'audit plus anciennes | aucune |
| `--similarity` | seuil de regroupement des sujets (0 à 1) | `0.6` |
| `--count-unexpected-answers` | compter aussi les « refus attendu, réponse donnée » | non |
| `--no-write` | résumé sans écrire le fichier | |

Code : `from gaps import run; report, path = run(audit_db=..., eval_report=...)`.
Codes de sortie : `0` succès ; `1` erreur (message clair sur stderr, aucun rapport partiel écrit).

## Contenu

| Fichier | Rôle |
|---|---|
| `readers.py` | lecture de `audit.db` (lecture seule), `GET /gaps`, `eval_report.json`, `questions.json` |
| `classify.py` | quels échecs de T1 révèlent un document manquant |
| `text.py` | normalisation, synonymes, similarité des sujets, masquage des données personnelles |
| `analyzer.py` | fusion, regroupement, classement, suggestions |
| `knowledge.py` | **règles métier à relire** : sous-domaines, documents et institutions suggérés |
| `report.py` | validation du contrat et écriture atomique |
| `pipeline.py`, `cli.py` | enchaînement et ligne de commande |
| `mocks.py`, `examples/` | faux `audit.db` (10 lacunes), faux `eval_report.json`, faux `questions.json`, exemple de rapport |

Documentation détaillée, hypothèses et points à caler : `RAPPORT_PHASE4_T2.md`.

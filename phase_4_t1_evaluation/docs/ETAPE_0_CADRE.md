# Étape 0 — Cadre Phase 4 T1 (Évaluation)

Date : 2026-11-08  
Branche : `champy`  
Dossier livrable : `phase_4_t1_evaluation/`

## 1. Constat d’inspection du dépôt

| Élément | Résultat |
|---|---|
| Module `evaluation/` | Absent avant cette étape (créé ici en squelette) |
| Endpoint `POST /ask` | **Introuvable** sur `champy`, `main` et branches inspectées |
| API HTTP disponible | Phase 2 : `POST /documents/upload`, `GET /health` |
| Phase 3 actuelle | `route_question()` Python dans `phase_3/` — **pas** d’HTTP `/ask` |
| Recherche RAG (`main`) | `backend.rag.search(query)` — CLI `search_demo.py`, pas `/ask` |

## 2. Blocage principal

Le guide Phase 4 T1 exige d’appeler l’API Phase 3 via **`POST /ask`** pour comparer :
- sources attendues vs obtenues (`source_hit_rate`) ;
- refus corrects (`correct_refusal_rate`) ;
- durées (`avg_duration_ms`).

Sans contrat réel de `/ask`, on ne peut pas finaliser le comparateur de sources.

## 3. Décision de travail (Étape 0)

**Option retenue pour avancer : B — client configurable + mode mock.**

- Développement du module `evaluation/` dans ce dossier uniquement.
- URL réelle via variable d’environnement `EVAL_API_BASE_URL` (jamais en dur).
- Mode `mock` pour les tests unitaires et le développement sans serveur.
- Dès que l’équipe livre `POST /ask`, on branche le client HTTP sur le contrat officiel **sans changer** le format de rapport Phase 4.

**Option A** (attendre `/ask`) reste possible : dans ce cas, geler l’étape 3 jusqu’au contrat.

## 4. Contrat de rapport (Phase 4 — imposé)

Champs obligatoires du rapport :

- `run_id`
- `n_questions`
- `metrics.source_hit_rate`
- `metrics.correct_refusal_rate`
- `metrics.avg_duration_ms`
- `failures[]` avec `question_id`, `expected`, `got`, `request_id`

Aucun champ obligatoire inventé au-delà de ce contrat.

## 5. Contrat provisoire `POST /ask` (à remplacer)

En attendant le contrat officiel, le client prévoira ce modèle **documenté comme provisoire** :

### Requête (provisoire)

```json
{
  "question": "Comment obtenir une CNI ?",
  "language": "fr"
}
```

### Réponse (provisoire)

```json
{
  "request_id": "REQ-...",
  "answer": "...",
  "refused": false,
  "sources": [
    {
      "document_id": "DOC-...",
      "chunk_id": "DOC-...-C001",
      "source_page": 1
    }
  ],
  "duration_ms": 123
}
```

Dès réception du contrat officiel Phase 3, ce schéma sera aligné ; le rapport `eval_report.*` restera stable.

## 6. Dénominateurs métriques (intention — à implémenter étape 4)

| Métrique | Numérateur | Dénominateur |
|---|---|---|
| `source_hit_rate` | questions où au moins une source attendue est retrouvée | questions **non-refus** avec `expected.sources` non vide |
| `correct_refusal_rate` | questions où refus attendu **et** refus obtenu | questions avec `expected.refused == true` |
| `avg_duration_ms` | somme des durées des appels **réussis HTTP** | nombre d’appels HTTP réussis (pas les erreurs réseau) |

Une erreur réseau / timeout / 5xx **n’est pas** un refus correct : elle va dans `failures` (ou une catégorie d’erreur d’exécution), pas dans le dénominateur « refusal ».

## 7. Sécurité (rappel)

- Pas de secrets / URL en dur.
- Données de test fictives uniquement.
- Pas de PII dans les rapports.
- Timeouts HTTP.
- Pas de `eval` / `exec` / commandes shell.
- Pas d’écrasement silencieux des rapports (suffixe `run_id`).

## 8. Périmètre strict

Toucher uniquement : `phase_4_t1_evaluation/`.

Ne pas modifier : `main`, `phase_2/`, `phase_3/`, `backend/` racine (sauf décision explicite ultérieure de l’assembleur).

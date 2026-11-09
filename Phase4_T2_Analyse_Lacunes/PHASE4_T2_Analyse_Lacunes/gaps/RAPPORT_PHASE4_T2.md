# Rapport technique — Phase 4, tâche T2 : Analyse des lacunes

**Projet :** Cameroun Public Service AI — Hackathon ITU AI for Good 2026 — Équipe HEMLE

## 1. Rôle

La Phase 3 note chaque question sans réponse dans la table `gaps` de `audit.db`. T1 (Phase 4) mesure la
qualité et liste ses échecs. T2 transforme ces signaux en **liste de travail priorisée** pour T3 :
*quels sujets manquent, combien de fois, quel document chercher, auprès de quelle institution.*

```
audit.db / GET /gaps ─┐
                      ├─► T2 ─► data/reports/gap_report.json ─► T3 (comble) ─► T1 (avant/après) ─► T4 (Qualité)
eval_report.json (T1)─┘
```

## 2. Sortie : `data/reports/gap_report.json`

Les clés du contrat du guide sont conservées à l'identique (`report_date`, `n_gaps`, `gaps[]` avec `gap_id,
topic, domain, occurrences, source, suggested_document, suggested_institution`). Ajouts, ignorables :

| Champ | Contenu |
|---|---|
| `gaps[].subdomain` | `national_identity_card`, `passport`, `driving_license`, `civil_status`, `taxes`, `public_treasury`, `personal_data_protection`, `general` |
| `gaps[].topic_key` | clé stable du sujet (ex. `national_identity_card:cni-frais`) |
| `gaps[].evidence` | `audit_occurrences`, `eval_occurrences`, `eval_failures`, `reasons`, `failure_types`, `example_questions` (3 max, masquées), `request_ids`, `question_ids`, `first_seen`, `last_seen` |
| `summary` | total des occurrences et décompte par sous-domaine |
| `inputs` | ce qui a été lu (chemins, nombre de lignes, `run_id` de T1) |
| `ignored_failures` | échecs de T1 écartés, avec la raison |
| `warnings` | tout ce que l'équipe doit savoir (source absente, texte introuvable...) |
| `parameters` | `since`, `similarity`, `count_unexpected_answers`, `source` |

`source` vaut `audit`, `eval` ou `audit+eval`. Extrait de l'exemple livré (`examples/gap_report_example.json`) :

```json
{"gap_id": "GAP-001", "topic": "frais CNI", "domain": "public_services",
 "subdomain": "national_identity_card", "occurrences": 4, "source": "audit+eval",
 "suggested_document": "barème des frais", "suggested_institution": "DGSN (à confirmer)"}
```

`gap_id` suit le classement **de cette exécution** (GAP-001 = la plus fréquente) : il change si on relance
après de nouvelles données. T3 doit citer dans `gaps_addressed` les `gap_id` du rapport qu'il a lu ;
`topic_key` sert à retrouver le même sujet d'un rapport à l'autre.

## 3. Méthode

1. **Lire** `gaps` (colonnes détectées par nom, voir §6), plus `audit_log` s'il existe pour retrouver la question
   et le routage (domaine, sous-domaine) de chaque requête. Base ouverte en **lecture seule**.
2. **Classer les échecs de T1** (`classify.py`) :

| Attendu | Obtenu | Type | Compté comme lacune ? |
|---|---|---|---|
| une source | `refused` | `source_missing` | oui |
| une source | `partial` | `partial_answer` | oui |
| une source | `approved` (autre document) | `wrong_source` | oui |
| `refused` | `approved` / `partial` | `unexpected_answer` | **non** : défaut de garde-fous, rien à collecter ; listé dans `ignored_failures` (option `--count-unexpected-answers` pour le compter) |

3. **Éviter le double comptage.** T1 interroge `POST /ask`, donc une question en échec crée déjà une ligne
   dans `gaps`. Un échec de T1 dont le `request_id` est déjà dans l'audit **confirme** la lacune (preuve
   `eval_failures`) sans ajouter d'occurrence.
4. **Regrouper** par sous-domaine puis par sujet : minuscules, sans accents, mots vides retirés, synonymes
   ramenés à un concept (coût, prix, tarif, montant → FRAIS ; délai, durée → DELAI...), pluriels retirés,
   puis similarité d'ensembles de mots (seuil 0,6). « coût du permis », « frais du permis de conduire » et
   « Combien coûte le permis de conduire pour un étudiant ? » forment ainsi une seule lacune. Des
   sous-domaines différents ne fusionnent jamais.
5. **Classer** par occurrences décroissantes ; à égalité : confirmée par T1, puis plus récente, puis clé.
6. **Suggérer** (`knowledge.py`) : le type de document selon les concepts du sujet (FRAIS → « barème des
   frais », DELAI → « texte ou note officielle fixant les délais », PIECES → « liste officielle des pièces à
   fournir »...) et l'institution selon le sous-domaine, toujours suffixée **« (à confirmer) »** ; « à
   confirmer » seul si le sous-domaine est inconnu.

## 4. Garanties

- **Aucune donnée personnelle dans le rapport** : téléphones, numéros de 8 chiffres ou plus et e-mails sont
  masqués dès la lecture (`[NUMERO_MASQUE]`, `[EMAIL_MASQUE]`).
- **Déterministe** : mêmes entrées, même rapport (hors `report_date`).
- **Écriture atomique et validée** : le rapport est validé (`validate_report`) avant écriture, écrit dans un
  fichier temporaire puis substitué ; un rapport invalide n'écrase jamais l'ancien.
- **Résilient** : sources facultatives (`eval_report.json`, `questions.json`) ; repli sur `GET /gaps` si
  `audit.db` est inutilisable ; échec d'une ligne = ligne ignorée et comptée, pas d'arrêt. Une erreur de
  source obligatoire donne un message explicite et le code de sortie 1.
- **Sans effet sur les autres phases** : lecture seule de `audit.db`, aucun import de `backend/`.

## 5. Tests

`python -m pytest tests/gaps` → **87 tests**, sans réseau : texte et synonymes, classement des échecs,
lecteurs (schémas alternatifs, dates ISO et epoch, filtre `--since`, base absente ou corrompue, lecture seule
vérifiée octet par octet, `GET /gaps` simulé), analyseur (fusion, double comptage, tri, égalités, masquage,
déterminisme), contrat et écriture atomique, pipeline (emplacements par défaut, repli API, erreurs), CLI, et
cohérence des fichiers d'exemple. Le scénario de référence (10 lacunes inventées + 6 échecs de T1) donne
8 lacunes et 13 occurrences, vérifiées à la main.

## 6. Hypothèses à valider (le code de la Phase 3 n'était pas disponible)

| Sujet | Hypothèse | Où ajuster |
|---|---|---|
| Schéma de `audit.db` | table `gaps` avec au moins une colonne de sujet (`topic`) ; `request_id`, `reason`, date, domaine, compteur reconnus s'ils existent ; table `audit_log` facultative (`request_id`, `question`, `routing` en JSON) | `COLUMN_ALIASES` dans `readers.py` |
| `GET /gaps` | liste, ou objet avec une liste sous `gaps`/`items`/`results`/`data` ; compteur facultatif (`count`, `occurrences`...) | `parse_gaps_payload` dans `readers.py` |
| `eval_report.json` | `failures[]` avec `question_id`, `expected` (`"refused"` ou source : texte ou objet), `got` (statut `refused`/`partial`/`approved`), `request_id` | `classify.py` |
| Emplacements | `data/audit.db` (ou `data/metadata/audit.db`, `audit.db`) | `pipeline.py` / `--audit-db` |
| Institutions | DGSN (CNI, passeport), mairies (état civil), MINFI / Impôts, Trésor public, Présidence (données) : **hypothèses** | `knowledge.py` |

## 7. Points à caler

| Avec | Point |
|---|---|
| **T1** | Mettre le `request_id` dans chaque échec (sinon pas de dédoublonnage ni de texte de question) ; nommer les questions de `data/eval/questions.json` avec le même `question_id` (`id` ou `question_id`, texte dans `question`). |
| **T3** | Lire `gaps[]` dans l'ordre ; `suggested_document` et `suggested_institution` sont des pistes ; `evidence.example_questions` montre ce que les citoyens demandent. Citer les `gap_id` lus dans `gaps_addressed`. |
| **T4** | La page Qualité peut afficher `gaps[]`, `summary.by_subdomain` et `warnings`. |
| **Phase 3** | Confirmer le schéma réel de `gaps` / `audit_log` (§6) : si les colonnes diffèrent, une ligne à changer. |

## 8. Limites connues

- Le regroupement est lexical : deux formulations très différentes d'un même sujet peuvent rester séparées
  (`--similarity` plus bas pour fusionner plus, plus haut pour fusionner moins). Il ne comprend pas le sens
  comme le ferait un modèle d'embeddings.
- Un sujet sans mot-clé connu tombe dans `general` (signalé dans `warnings`) et reçoit « fiche officielle
  décrivant la procédure ».
- Avec `GET /gaps` seul, il n'y a pas de `request_id` : un échec de T1 peut être compté en double avec l'audit
  (signalé dans `warnings`). Préférer `audit.db`.
- Les institutions suggérées ne sont pas vérifiées : à confirmer avant toute collecte.

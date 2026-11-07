# Rapport technique — Phase 3, tâche T2 : Agents spécialisés

**Projet :** Cameroun Public Service AI — Hackathon ITU AI for Good 2026 — Équipe HEMLE

---

## 1. Rôle de la tâche

T2 reçoit le **plan de routage de T1** et la question du citoyen, interroge la base de connaissances
de la Phase 2 (`search`) et fait rédiger par un LLM un **brouillon sourcé** par agent. T2 ne valide
rien : la vérification (guardrails, seuil, données sensibles, lacunes) est le travail de T3.

```
T4 ── question + language ──► T1 ── plan de routage ──► T2 ◄── search() Phase 2
                                                         │
                                         brouillon(s) + sources
                                                         ▼
                                                   merge_drafts ──► T3 ──► T4
```

## 2. Entrées et sorties

### Entrées
| Entrée | Origine | Contenu |
|---|---|---|
| `routing_plan` | sortie de T1 (contrat du guide) | `request_id, intent, domain, subdomain, agents, needs_clarification` |
| `question`, `language` | requête reçue par T4 | texte du citoyen, `fr` ou `en` (défaut `fr`) |
| `search(query, top_k)` | Phase 2 (`backend/rag`) | liste de `{rank, score, distance, chunk_id, document_id, text, source_page}` |
| `llm_generate(prompt)` | point d'entrée LLM commun | texte (voir §6) |

> Le plan de T1 ne contient **pas** le texte de la question. T4 doit donc transmettre `question`
> (et `language`) à T2 en plus du plan : `run_agents(question, plan, language=...)`.

### Sortie : un brouillon par agent
```json
{
  "request_id": "REQ-20261106-0001",
  "agent": "procedure",
  "answer_draft": "Pour une première demande de CNI, préparez ... [1]. Venez avec les originaux ... [2].",
  "citations": [{"chunk_id": "DOC-...-C005", "document_id": "DOC-...", "source_page": 2}],
  "retrieval": {"top_score": 0.71, "n_chunks": 4, "passages": [ ... ]},
  "meta": {"kind": "rag", "language": "fr", "no_answer": false}
}
```
Les clés du guide sont respectées à l'identique. Deux **ajouts facultatifs** (ignorables) :

- `retrieval.passages` : les passages donnés au LLM (rang, score, chunk_id, document_id, source_page, texte).
  T3 en a besoin pour vérifier que les citations et les chiffres existent vraiment ; T4 pour la colonne
  « passages » du journal d'audit.
- `meta` : `kind` (`rag`, `static`, `error`), `language`, `no_answer`, et selon le cas
  `admits_missing_info`, `invalid_citations_removed`, `sensitive_data_masked`, `question_truncated`, `reason`, `error`.

**Règle des renvois.** `[k]` dans `answer_draft` désigne exactement `citations[k-1]`. Le LLM reçoit des
passages numérotés ; T2 supprime ses renvois invalides, renumérote les autres dans l'ordre d'apparition et
ne garde dans `citations` que les passages réellement cités. `top_score` est le meilleur score parmi tous
les passages récupérés.

Un exemple complet est dans `examples/t2/` (`input_agents_example.json`, `output_agents_example.json`).

## 3. Les agents

| Agent (`agent`) | Mission | Particularité |
|---|---|---|
| `procedure` | étapes, pièces, délais, frais, lieu | prompt orienté liste numérotée |
| `juridique` | lois, décrets, arrêtés | références reprises telles quelles, pas de conseil personnalisé |
| `donnees_personnelles` | protection des données | requête de recherche enrichie ; ne demande jamais de données |
| `anti_fraude` | faux intermédiaires, paiements | requête enrichie ; canaux officiels cités seulement s'ils sont dans les passages |
| `accueil` | bienvenue, précision, hors sujet | **sans recherche ni LLM** : messages fixes FR/EN |

Noms acceptés dans le plan de T1 (accents, tirets, majuscules tolérés) : `protection_donnees`,
`protection_des_donnees` → `donnees_personnelles` ; `fraude`, `antifraude` → `anti_fraude`. Un nom
inconnu est ignoré avec un avertissement (`strict=True` lève `UnknownAgentError`). `coordinateur`
n'est pas un agent de T2 : il est ignoré (l'assemblage final se fait via `merge_drafts`, T3 et T4).

**Routage.** `needs_clarification = true` → `accueil` (question de précision) ; intention `accueil` ou
`hors_sujet` → `accueil` seul ; sinon les agents du plan, dans l'ordre, sans doublon, **3 au maximum**.

## 4. Principes anti-erreurs

1. **Réponse uniquement depuis les passages.** Le prompt interdit toute connaissance extérieure et tout
   montant, délai ou référence absent des passages ; il impose la phrase *« Je ne dispose pas d'information
   officielle sur ce point dans les documents consultés. »* (détectée ensuite : `no_answer`, ou
   `admits_missing_info` si la réponse est partielle).
2. **Aucun passage → aucun appel LLM.** Le brouillon est la phrase d'ignorance, sans citation.
3. **Contenu des passages = donnée, pas instruction** (protection contre l'injection de consignes).
4. **Données personnelles masquées avant le LLM.** Numéros de téléphone, suites de 8 chiffres ou plus
   (CNI, dossier), e-mails sont remplacés par `[NUMERO_MASQUE]` / `[EMAIL_MASQUE]` dans la recherche
   et dans le prompt. Les montants (`10.000 FCFA`), dates et durées ne sont pas touchés.
5. **Pannes sans effondrement.** Si un agent échoue (index absent, LLM indisponible), son brouillon porte
   `meta.kind = "error"` et `meta.error` ; les autres agents continuent. `strict=True` lève l'exception.
6. **Une seule recherche par requête distincte** pour tous les agents d'une même question.
7. **Typographie française préservée** lors du nettoyage des renvois (espaces avant `: ; ? !`).

## 5. Fusion pour T3 (`merge_drafts`)

T3 reçoit « le brouillon » au singulier. Quand T1 désigne plusieurs agents, `merge_drafts` (sans LLM)
produit un seul brouillon au même contrat : sections étiquetées (« Procédure : », « Textes officiels : »),
citations dédoublonnées par `chunk_id`, renvois recalculés, `top_score` = maximum, passages réunis. Un agent
sans réponse n'apparaît pas dans le texte mais le signale (`admits_missing_info`). Avec un seul brouillon, il
est renvoyé inchangé (+ `meta.agents`).

## 6. Point d'entrée LLM

`llm_generate(prompt) → texte` (`backend/agents/llm.py`). **Le choix du LLM n'est pas imposé** : deux
fournisseurs sont prévus, `openai_compatible` (OpenAI, Ollama, vLLM, Groq...) et `anthropic`, réglés par
variables d'environnement (`llm.env.example`). Nouvelles tentatives sur erreur réseau, 429 et 5xx ;
les erreurs 4xx ne sont pas rejouées ; la clé n'apparaît jamais dans les messages d'erreur.
`set_llm(fonction)` remplace le moteur (tests, autre fournisseur) sans toucher aux agents.

## 7. Structure livrée

```
backend/agents/
├── __init__.py      # exports : run_agents, merge_drafts, validate_draft, llm_generate, set_llm ...
├── base.py          # classe Agent, validation des passages, assemblage du brouillon
├── agents.py        # Procedure, Juridique, DonneesPersonnelles, AntiFraude, Accueil
├── prompts.py       # gabarit : consigne + règles + passages numérotés + question
├── runner.py        # run_agents : routage, alias, cache de recherche, gestion des pannes
├── merge.py         # merge_drafts
├── contract.py      # validate_draft (comme chunking/validate.py)
├── citations.py     # normalisation / renumérotation des [n]
├── privacy.py       # masquage des données personnelles
├── messages.py      # textes fixes FR/EN
├── llm.py           # llm_generate
├── mocks.py         # faux search() + FakeLLM (test de T2 seul)
├── cli.py           # python -m backend.agents.cli
└── exceptions.py
tests/agents/        # 85 tests
examples/t2/         # 12 plans T1 simulés, 4 passages Phase 2, exemples d'entrée / sortie
```

## 8. Tests

`python -m pytest tests/agents` → **85 passés**, sans modèle, sans réseau, sans clé. Ils couvrent : le
contrat de sortie, la correspondance `[k]` ↔ `citations[k-1]`, les renvois invalides, l'absence de passage,
la phrase d'ignorance et la réponse partielle, le masquage, l'injection, chaque agent, les alias et le
routage, le cache de recherche, les pannes, la fusion, le LLM (requêtes OpenAI/Anthropic simulées, reprises,
erreurs), la CLI, et 3 tests branchés sur le **vrai** `VectorStore`/FAISS de la Phase 2 (faux embedder).
Les 12 plans simulés de `examples/t2/routing_plans_mock.json` (9 questions métier, plus accueil, précision
de la demande et hors sujet) passent tous par `run_agents`.

**Non testé ici, à faire chez vous :** le vrai modèle `BAAI/bge-m3` et un vrai LLM (pas d'accès réseau
dans mon environnement). Le code est prêt ; il faut `build_index` puis les variables `LLM_*`.

## 9. Points à caler avec T1, T3 et T4

| Avec | Point |
|---|---|
| **T4** | Transmettre `question` et `language` à T2 (absents du plan T1). Appeler `run_agents` puis `merge_drafts`. Stocker `retrieval.passages` dans `audit_log`. Si `meta.kind == "error"`, prévoir un message d'indisponibilité. |
| **T3** | Pour `meta.kind == "static"` (accueil), il n'y a ni citation ni score (`top_score = 0.0`) : ne pas appliquer le contrôle de seuil ni les « lacunes ». Pour `meta.no_answer` ou `admits_missing_info`, créer la lacune (`gap`). `retrieval.passages` permet de vérifier l'ancrage. |
| **T1** | Noms d'agents : `procedure`, `juridique`, `donnees_personnelles`, `anti_fraude`, `accueil` (alias acceptés). Pas plus de 3 agents. |
| **Phase 2** | `data/indexes/faiss.index` d'exemple = 384 dimensions, `bge-m3` = 1024 : reconstruire l'index (`config.py` indique encore `EMBEDDING_DIM = 384`). Le seuil de T3 (ex. 0,35) doit être calibré sur les scores réels de `bge-m3`. |

## 10. Limites connues

- Le contrôle de la fidélité des chiffres (montants, délais) revient à T3 ; T2 limite le risque par le prompt
  et fournit les passages pour la vérification.
- Si le LLM ne reprend pas la phrase d'ignorance mot pour mot (paraphrase), `no_answer` n'est pas détecté :
  T3 voit alors une réponse sans citation.
- Les agents `donnees_personnelles` et `anti_fraude` ne seront utiles que si la base contient des documents
  sur ces sujets (la loi n° 2024/017 et les alertes anti-fraude ne sont pas encore dans `01_CNI/`).
- Le masquage repose sur des motifs (téléphones camerounais, 8 chiffres et plus, e-mails) : il ne détecte pas
  les noms propres.
- Un passage de la plaquette DGSN à cheval sur deux pages ne cite que sa page de début (limite de T3, Phase 2).

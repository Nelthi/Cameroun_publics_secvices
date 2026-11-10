# Rapport technique : Phase 3, Tâche T4 (API, Audit et Interface)

Projet Cameroun Public Service AI, équipe HEMLE, Hackathon ITU AI for Good 2026

## 1. Rôle de T4

T4 est la porte d'entrée (la question arrive par l'API), la porte de sortie (la réponse repart par elle) et la mémoire du système (journal d'audit). Elle ne comprend pas la question (T1), ne rédige pas la réponse (T2) et ne la vérifie pas (T3) : elle **appelle ces trois étapes dans l'ordre** et garde une trace complète.

```
Interface Streamlit --POST /ask--> API --> pipeline.run
                                             T1 route_question(payload)        -> routage
                                             T2 run_agents(routing, question)  -> brouillon + sources
                                             T3 validate_answer(draft, q)      -> réponse validée + lacunes
                                           audit SQLite (audit_log + gaps)
Interface <------ réponse + sources ------ API
```

## 2. Contrats (voir app/schemas.py)

| Étape | Entrée | Sortie (champs obligatoires) |
|---|---|---|
| T1 | payload : request_id, question, language, timestamp | request_id, intent, agents (+ domain, subdomain, needs_clarification) |
| T2 | sortie de T1 + question | request_id, answer_draft (+ agent, citations, retrieval) |
| T3 | sortie de T2 + question | request_id, status (approved/partial/refused), final_answer (+ citations, checks, gaps) |
| T4 | question du citoyen | request_id, status, answer, sources, timestamp |

Les modèles Pydantic acceptent des champs **en plus** (tolérance) mais refusent un champ obligatoire manquant ou mal typé, avec un message qui nomme l'étape et le champ.

## 3. Fonctionnement, module par module

- **config.py** : message d'erreur, de refus, de clarification; longueur maximale (500 caractères); chemin de la base (`AUDIT_DB`) et délai par étape (`STAGE_TIMEOUT`, 60 s par défaut).
- **schemas.py** : les contrats ci-dessus.
- **mocks.py** : faux T1, T2, T3. Une question sur la CNI donne une réponse approuvée (score 0.71, source DOC-EXEMPLE-CNI page 1); une autre donne un refus (score 0.18) avec une lacune; une question de moins de 3 mots demande une précision.
- **stages.py** : les trois portes `route_question`, `run_agents`, `validate_answer`. Variables `T1_IMPL`, `T2_IMPL`, `T3_IMPL` (format `module:fonction`) pour brancher les vraies tâches une par une.
- **audit.py** : création des tables, `write_audit` (une transaction : ligne d'audit + lacunes), `get_audit`, `list_gaps` (lacunes regroupées par sujet), `mask_sensitive`.
- **pipeline.py** : le cœur. `run(question)` crée le `request_id` (REQ-AAAAMMJJ-xxxxxx, 6 caractères hexadécimaux pour éviter les collisions), appelle chaque étape avec un délai maximum, garde la sortie brute dans l'audit **avant** de la valider, puis écrit l'audit dans un bloc `finally` : il est donc écrit même en cas d'erreur.
- **main.py** : routes `POST /ask`, `GET /audit/{request_id}`, `GET /gaps`, `GET /health`.
- **ui/streamlit_app.py** : zone de question, réponse avec badge de statut, sources (document + page), détails techniques repliables, lacunes dans la barre latérale.

## 4. Deux questions suivies de bout en bout (avec les mocks)

**« Quelles sont les pièces pour la CNI ? »** : request_id créé; T1 : intent `procedure`; T2 : brouillon avec la citation `DOC-EXEMPLE-CNI-C001`, score 0.71; T3 : `approved`; audit : une ligne `approved`; réponse HTTP 200 avec `sources = [{"document_id": "DOC-EXEMPLE-CNI", "source_page": 1}]`.

**« Combien coûte un permis de conduire ? »** : T1 : `hors_sujet`; T2 : score 0.18; T3 : `refused` + lacune; audit : une ligne `refused`, une ligne dans `gaps`; réponse HTTP 200 `refused`, sans source.

## 5. Gestion des cas particuliers

| Situation | Comportement |
|---|---|
| Question vide, absente ou de plus de 500 caractères | HTTP 422 |
| T1 demande une précision | status `needs_clarification`, T2 et T3 non appelées, HTTP 200 |
| T3 refuse | HTTP 200, status `refused`, sources vides, lacune enregistrée |
| Étape en exception, trop lente ou JSON non conforme | HTTP 503, status `error`, message neutre à l'utilisateur, détail dans la colonne `error` de l'audit |
| Échec d'écriture de l'audit | enregistré dans les logs, la réponse part quand même |
| Numéro de 8 chiffres ou plus dans la question | masqué dans `audit_log.question` (`[NUMÉRO MASQUÉ]`) |

## 6. Choix et limites (à valider avec l'équipe)

1. **Masquage** : T4 masque les numéros dans la question stockée. Il ne masque pas les autres colonnes (sorties de T2 et T3), qui peuvent reprendre la question. À régler avec le membre 3.
2. **Plusieurs agents** : T4 attend UN brouillon de T2 (liste d'agents fusionnée en amont). Si T2 renvoie une liste, il faudra modifier `AgentOut` et `pipeline.py`.
3. **Pas d'asynchrone** : une requête à la fois par thread. Suffisant pour la démonstration; si les réponses du LLM sont lentes, on pourra passer en asynchrone.
4. **Délai** : un thread bloqué ne peut pas être tué; le délai libère seulement la réponse (503). Un appel LLM trop lent continue donc en arrière-plan jusqu'à son terme.
5. **Pas d'authentification** sur l'API et sur `/audit` : acceptable pour le hackathon, pas pour la production.
6. **`source_page` doit être un entier** (comme en Phase 2). Un autre type est refusé.

## 7. Tests (`python -m pytest -q` : 12 tests)

Réponse approuvée avec sources et audit; refus avec lacune; regroupement des lacunes; clarification sans appel de T2/T3; exception d'une étape (503 + audit); contrat violé (étape et champ nommés, sortie brute gardée); délai dépassé; questions invalides; masquage; identifiants non masqués par erreur; `request_id` inconnu (404); route `/health`.

## 8. Intégration, pas à pas

1. Lancer l'API avec les mocks, vérifier l'interface.
2. Quand T1 est livré : `export T1_IMPL="module:fonction"`, relancer, tester.
3. Même chose pour T2, puis T3.
4. Si une vraie tâche casse tout, retirer sa variable : le mock reprend la place.
5. Test final avec 10 vraies questions (approuvées, refusées, avec numéro de téléphone, hors sujet).

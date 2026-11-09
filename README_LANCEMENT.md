# Lancement et démonstration du projet fusionné

Projet **Cameroun Public Service AI** · Phase 2 Base de connaissances · Équipe HEMLE

Ce document sert à **exécuter la fusion de bout en bout** et à la présenter : on téléverse un document, on suit son parcours à travers les 4 tâches, et on termine en posant une question de citoyen dont la réponse vient du document qu'on vient d'ajouter. À chaque étape, on peut constater qui a produit quoi, et **identifier la tâche responsable** si quelque chose échoue.

```
 Champy (T1)          Nelson (T2)          Alex (T3)            Didier (T4)           Citoyen
 Ingestion     ───►   Extraction    ───►   Découpage     ───►   Vectorisation  ───►   pose une
 et stockage          et nettoyage         en fragments         + index FAISS         question
 data/raw/            data/processed/      data/chunks/         data/indexes/         search_demo.py
 + SQLite
```

Toutes les commandes se lancent **depuis la racine du projet** (le dossier qui contient `backend/`, `chunking/`, `tests/`).

---

## 0. Préparation (une seule fois)

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git
unzip Projet_fusionne.zip && cd merged

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

À chaque nouveau terminal : `cd merged && source .venv/bin/activate`.

Prévoir environ 5 Go de disque et 6 Go de RAM pour la machine virtuelle : le modèle `BAAI/bge-m3` de T4 est téléchargé (environ 2,3 Go) au premier usage, puis gardé en cache.

**Vérification rapide avant la démonstration** (sans modèle, sans réseau) :

```bash
python -m pytest -q          # attendu : 61 passed, 1 skipped
```

**Partir d'un état propre** (pour que la démonstration ne mélange pas les anciens fichiers) :

```bash
rm -rf data/raw/* data/processed/* data/metadata/*
mkdir -p /tmp/exemples && mv data/chunks/chunks_exemple*.json /tmp/exemples/
```

La 2e commande met de côté les fragments d'exemple de T4, pour que l'index ne contienne que le document de la démonstration.

---

## 1. T1 : Champy, ingestion et stockage

**Ce que Champy a livré :** une **API** (FastAPI), pas une interface web complète. FastAPI génère automatiquement une page de test dans le navigateur (**Swagger**), où l'on peut téléverser un fichier sans écrire de code. On peut aussi appeler la même route avec Postman ou `curl`. T1 ne fait que **stocker et cataloguer** : il ne lit jamais le contenu du document et ne déclenche rien derrière lui.

### 1.1 Lancer l'API

```bash
uvicorn backend.knowledge_base.api.app:app --host 127.0.0.1 --port 8000
```

Laisser ce terminal ouvert. Dans un navigateur :

- http://127.0.0.1:8000/health doit afficher `{"status":"ok","module":"T1"}`
- http://127.0.0.1:8000/docs ouvre la page Swagger.

### 1.2 Téléverser un document

Dans Swagger : `POST /documents/upload` → **Try it out** → choisir le fichier → remplir les champs → **Execute**.

| Champ | Valeur pour la démonstration |
|---|---|
| `file` | `01_CNI/Plaquette-20-Mai-2025-FR-ok.pdf` |
| `title` | `Plaquette CNI` |
| `institution` | `DGSN` |
| `date` | `2025-05-20` |
| `domain` | `public_services` |
| `subdomain` | `national_identity_card` |

Équivalent en ligne de commande (nouveau terminal, depuis la racine) :

```bash
curl -X POST "http://127.0.0.1:8000/documents/upload" \
  -F "file=@01_CNI/Plaquette-20-Mai-2025-FR-ok.pdf" \
  -F "title=Plaquette CNI" -F "institution=DGSN" -F "date=2025-05-20" \
  -F "domain=public_services" -F "subdomain=national_identity_card"
```

### 1.3 Ce qu'on doit voir

Réponse **HTTP 201** avec un identifiant, par exemple :

```json
{"document_id": "DOC-73EF2E8F", "original_filename": "Plaquette-20-Mai-2025-FR-ok.pdf",
 "stored_path": "data/raw/public_services/national_identity_card/DOC-73EF2E8F.pdf",
 "domain": "public_services", "institution": "DGSN", "status": "stored", ...}
```

**Noter le `document_id`** : c'est le fil conducteur de toute la suite. Dans la suite, remplacer `DOC-XXXXXXXX` par cet identifiant (T1 génère un nouvel identifiant à chaque contenu différent).

Constat à montrer :

```bash
ls data/raw/public_services/national_identity_card/        # le fichier, renommé avec son identifiant
python3 -c "
import sqlite3; c = sqlite3.connect('data/metadata/documents.sqlite3')
for r in c.execute('select document_id, original_filename, domain, subdomain, status from documents'): print(r)"
```

Le document est rangé dans `data/raw/` et catalogué dans la base SQLite. **Fin du travail de Champy** : les trois tâches suivantes prennent le relais, chacune dans son dossier. Envoyer deux fois le même fichier doit renvoyer le même identifiant avec **HTTP 200** (doublon détecté), sans créer de copie.

Arrêter l'API (Ctrl+C) : elle n'est plus nécessaire.

---

## 2. T2 : Nelson, extraction et nettoyage

Nelson lit le registre de Champy, ouvre le fichier brut dans `data/raw/`, extrait le texte **page par page** (PDF) et le nettoie (espaces, retours à la ligne), en conservant accents et ponctuation.

```bash
python -m backend.knowledge_base.processors.cli DOC-XXXXXXXX
```

Ce qu'on doit voir : `"status": "processed"`, un `character_count` supérieur à 0, un nombre de segments (= pages avec texte) et `"warnings": []`.

```bash
ls data/processed/public_services/national_identity_card/
python -m json.tool data/processed/public_services/national_identity_card/DOC-XXXXXXXX.json | head -40
```

Le JSON contient la provenance (`source`), les métadonnées de Champy (`metadata`) et le texte par page (`content.segments`, avec `page_number`).

*Cas à connaître :* un PDF scanné donne `"status": "needs_ocr_or_review"` avec un avertissement : c'est prévu, il faudra un OCR (hors périmètre de la phase 2).

---

## 3. T3 : Alex, découpage en fragments

Alex prend le texte nettoyé et le découpe en fragments de **800 caractères** avec **120 de chevauchement**, coupés sur une fin de phrase quand c'est possible, chacun avec la page où il commence.

La sortie de T2 est organisée en `content.segments` alors que T3 attend `pages[]` : une petite commande de liaison (`backend/pipeline/`, ajoutée à la fusion) fait la conversion, puis appelle le code d'Alex.

```bash
python -m backend.pipeline.t2_to_t3 DOC-XXXXXXXX
python -m chunking.validate data/chunks/DOC-XXXXXXXX.json
```

Ce qu'on doit voir : `21 fragments -> data/chunks/DOC-XXXXXXXX.json` (le nombre exact dépend du document) puis `OK : le fichier respecte le contrat T3`.

```bash
python -m json.tool data/chunks/DOC-XXXXXXXX.json | head -30
```

Chaque fragment a : `chunk_id` (`DOC-XXXXXXXX-C001`…), `text` (800 caractères maximum), `source_page`, `position`. **Fin du travail d'Alex** : il a produit le fichier que Didier consomme.

---

## 4. T4 : Didier, vectorisation et index FAISS

Didier transforme chaque fragment en vecteur de **1024 nombres** avec `BAAI/bge-m3` et les range dans un index FAISS, avec un fichier de correspondance (numéro de vecteur → fragment, document, page).

```bash
python -m backend.rag.build_index
```

Au premier lancement, le modèle est téléchargé (plusieurs minutes). Ce qu'on doit voir : `N fragments lus, 1 document(s). Vectorisation...` puis `Index : data/indexes/faiss.index (N vecteurs, dim 1024)`. **N doit être égal au nombre de fragments produits par T3.**

```bash
ls -la data/indexes/       # faiss.index + chunk_mapping.json
```

---

## 5. Le test final : un citoyen pose une question

C'est ici qu'on voit **l'utilité de la chaîne** : la réponse provient du document téléversé à l'étape 1, retrouvée par le sens (pas par mots-clés exacts), avec sa page d'origine.

```bash
python search_demo.py "Puis-je changer la date de mon enrôlement ?" -k 4
```

Pour chaque résultat : rang, score (0 à 1, plus haut = plus proche), identifiant du fragment, page, début du texte. Avec la plaquette CNI, le premier résultat doit être le fragment qui contient « *une seule fois* » (le droit de changer la date d'enrôlement physique).

Autres questions pour la présentation, avec le contenu attendu dans les premiers résultats :

| Question du citoyen | Contenu attendu dans les fragments |
|---|---|
| `Combien de temps faut-il pour produire ma carte d'identité ?` | la CNI est produite en **48 heures** après validation |
| `Quelqu'un d'autre peut-il retirer ma carte à ma place ?` | retrait possible par un **tiers muni d'une procuration légalisée** |
| `Comment faire le pré-enrôlement en ligne ?` | le site **idcam.cm**, choix de la langue, code reçu par SMS ou mail |

Depuis du code (c'est ce qu'utiliseront les agents de la phase 3) :

```python
from backend.rag import search
for r in search("Puis-je changer la date de mon enrôlement ?", top_k=4):
    print(r["rank"], r["score"], r["chunk_id"], "page", r["source_page"])
```

**Si ces réponses sortent, la chaîne complète fonctionne** : un document ajouté par l'API est devenu une connaissance interrogeable.

---

## 6. En cas d'erreur : trouver la tâche responsable

Une règle simple : **suivre une phrase précise d'étape en étape** et voir où elle disparaît. Exemple avec « 48 heures » :

```bash
grep -c "48 heures" data/processed/public_services/national_identity_card/DOC-XXXXXXXX.json   # T2
grep -c "48 heures" data/chunks/DOC-XXXXXXXX.json                                              # T3
```

| Ce qu'on observe | Tâche à examiner | Vérification |
|---|---|---|
| `/health` ne répond pas, upload refusé (400 / 415), fichier absent de `data/raw/`, ligne absente du registre SQLite | **T1 Champy** | section 1.3 |
| `status` différent de `processed`, `character_count` à 0, texte absent ou déformé dans `data/processed/...json` | **T2 Nelson** | section 2 |
| Phrase présente dans T2 mais absente de `data/chunks/...json`, `chunking.validate` en erreur, fragments de plus de 800 caractères, mauvaise `source_page` | **T3 Alex** | section 3 |
| Phrase présente dans les fragments mais la recherche ne la remonte pas, nombre de vecteurs différent du nombre de fragments, erreur de dimension, score incohérent | **T4 Didier** | section 4 et 5 |
| Erreur à la conversion T2 → T3 (`t2_to_t3`) alors que T2 et T3 fonctionnent chacun | **Liaison de la fusion** (`backend/pipeline/`, côté chef de projet) | `NOTES_FUSION.md` |

Constats à mettre dans la critique croisée :

- **Contrat respecté ?** Chacun doit livrer les champs exacts du guide (snake_case, dates ISO 8601, dossiers `data/raw`, `data/processed`, `data/chunks`, `data/indexes`).
- **Limites connues, à discuter en équipe :**
  - T3 attribue à un fragment la page où il **commence** ; un fragment à cheval sur deux pages cite seulement la première (environ 1 fragment sur 4 sur les PDF testés). Option : ne pas franchir les pages.
  - T2 ne fait pas d'OCR : un PDF scanné donne zéro fragment.
  - T4 : l'index doit être reconstruit à chaque nouveau document (`build_index`).

## 7. Problèmes fréquents

| Symptôme | Cause et solution |
|---|---|
| `externally-managed-environment` | `pip` utilisé hors du venv : `source .venv/bin/activate`. |
| `ModuleNotFoundError: backend` ou `chunking` | Commande lancée hors de la racine du projet. |
| `Aucun fichier T2 pour DOC-...` | T2 n'a pas encore traité ce document : refaire la section 2. |
| Téléchargement du modèle très lent ou bloqué | Vérifier la connexion et l'espace disque, relancer (reprise automatique). |
| `Killed` pendant la vectorisation | Mémoire insuffisante dans la VM : passer à 6 Go de RAM ou plus. |
| Erreur de dimension FAISS | Un ancien index (384 dimensions) est resté : relancer `python -m backend.rag.build_index`. |

## 8. Variante : tout enchaîner en une commande

Sans passer par l'API, pour vérifier rapidement que la chaîne tient :

```bash
python -m backend.pipeline.run "01_CNI/Plaquette-20-Mai-2025-FR-ok.pdf" \
  --title "Plaquette CNI" --institution DGSN --date 2025-05-20 \
  --domain public_services --subdomain national_identity_card
```

Elle fait T1 → T2 → T3 → T4 d'un coup, puis on enchaîne avec la section 5.

## 9. Publier sur GitHub

Une fois la démonstration validée :

```bash
git remote -v
git push -u origin main
```

Si `main` existe déjà sur GitHub avec un autre historique : `git pull origin main --allow-unrelated-histories` d'abord.

---

---
---

# PARTIE 3 : de la question du citoyen à la réponse sourcée

Cette partie suppose la **Partie 2 faite** (sections 0 à 5 ci-dessus) : un document téléversé, découpé, et un **index construit avec bge-m3** (`python -m backend.rag.build_index`). Sans index, les agents n'ont rien à chercher et toutes les questions sont refusées.

```
 Citoyen ─► T4 API (POST /ask) ─► T1 routage ─► T2 agents ─► T3 guardrails ─► T4 réponse + audit
 Streamlit    crée REQ-...        intention,     search()      vérifie, masque    + sources + lacunes
                                  agents         + LLM         refuse / valide
```

## P3.0 Préparation

```bash
source .venv/bin/activate
pip install -r requirements.txt          # ajoute streamlit et requests
python -m pytest -q                      # attendu : 271 passed, 1 skipped (Partie 2 + Partie 3)
```

## P3.1 Choisir le LLM (T2)

T2 appelle un seul point d'entrée, `llm_generate(prompt)`. **Aucun LLM n'est choisi par l'équipe pour l'instant**, il faut donc en configurer un, par variables d'environnement (détail dans `llm.env.example`) :

| Option | Commandes |
|---|---|
| **Test sans LLM** (réponse recopiée depuis le passage le plus proche, pas de génération) | aucune : utiliser `--demo-llm` à l'étape suivante |
| **Ollama en local** (gratuit, hors ligne) | `export LLM_PROVIDER=openai_compatible LLM_MODEL=<modèle> LLM_BASE_URL=http://localhost:11434/v1` |
| **API payante** | `export LLM_PROVIDER=openai_compatible LLM_MODEL=<modèle> LLM_API_KEY=<clé>` ou `LLM_PROVIDER=anthropic` + `LLM_MODEL` + `LLM_API_KEY` |

Le mode démonstration permet de présenter toute la chaîne, mais il ne **génère** rien : à ne pas présenter comme la réponse finale du projet.

## P3.2 Lancer l'API (T4 branchée sur T1, T2 et T3)

```bash
python -m backend.pipeline.serve --demo-llm        # ou, avec un vrai LLM configuré : python -m backend.pipeline.serve
```

Le lanceur affiche quelles tâches sont branchées, par exemple :

```
T1 : backend.pipeline.phase3:route_question
T2 : backend.pipeline.phase3:run_agents
T3 : backend.pipeline.phase3:validate_answer
LLM : DÉMO sans LLM (...)
```

**Ne pas lancer `uvicorn app.main:app` directement** : T4 utiliserait alors ses faux T1, T2 et T3 (`app/mocks.py`) et répondrait avec un document bidon `DOC-EXEMPLE-CNI`. Si tu vois ce nom dans une réponse, ce sont les faux.

Page de test : http://127.0.0.1:8000/docs. Deuxième terminal pour l'interface :

```bash
source .venv/bin/activate && streamlit run ui/streamlit_app.py      # http://localhost:8501
```

## P3.3 Poser des questions et suivre le parcours

Exemples (document de la Partie 2 : la plaquette CNI). Dans Streamlit ou :

```bash
curl -s -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" \
  -d '{"question": "Comment faire le pré-enrôlement en ligne pour la CNI ?"}'
```

| Question | Résultat attendu |
|---|---|
| `Comment faire le pré-enrôlement en ligne pour la CNI ?` | `approved`, réponse venant du site idcam.cm, **source : document + page** |
| `Quelles sont les pièces à fournir pour la CNI ?` | `approved`, avec les pièces du document |
| `Quel est le score du match de foot ?` | `refused` (hors sujet), aucune source, **une lacune enregistrée** |
| `Mon numéro de téléphone est 699123456, où retirer ma CNI ?` | `partial` ou `refused`, le numéro n'apparaît ni dans la réponse ni dans le journal |

La réponse contient `request_id`, `status`, `answer`, `sources`. Avec ce `request_id`, on voit **le travail de chaque tâche** :

```bash
curl -s http://127.0.0.1:8000/audit/REQ-XXXXXXXX-XXXXXX | python -m json.tool
```

| Champ de l'audit | Produit par | À regarder |
|---|---|---|
| `routing_json` | **T1** | `intent`, `domain`, `subdomain`, `agents` |
| `agent_outputs_json` | **T2** | `answer_draft` avec renvois `[1]`, `citations`, `retrieval.top_score`, `retrieval.passages` |
| `validation_json` | **T3** | `status`, `checks` (grounded, has_citations, score_ok, no_sensitive_data), `gaps` |
| `status`, `final_answer`, `duration_ms`, `error` | **T4** | l'enregistrement final, le temps, l'erreur d'étape s'il y en a une |

Les **lacunes** (ce que la base ne sait pas, donc quels documents ajouter) : `curl -s http://127.0.0.1:8000/gaps`.

## P3.4 En cas d'erreur : quelle tâche est responsable ?

| Ce qu'on observe | Tâche à examiner |
|---|---|
| Réponse avec `DOC-EXEMPLE-CNI` | **T4** : lancée sans le lanceur, donc avec les faux (P3.2) |
| `routing_json` : `hors_sujet`, `agents: []` pour une vraie question | **T1** : mots-clés de routage trop étroits |
| `error` : « T2 (agents) … » ou `agent_outputs_json` avec `meta.kind = error` | **T2** : recherche impossible (index absent ou mauvaise dimension) ou LLM non configuré |
| `agent_outputs_json` correct mais `validation_json` refuse ou retire des phrases | **T3** : voir `checks` et `gaps` pour la raison exacte |
| `validation_json` correct mais mauvaise réponse à l'écran ou HTTP 503 | **T4** : API, audit ou interface |
| Passages non pertinents dans `retrieval.passages` | **Partie 2** (T3 découpage ou T4 vectorisation), pas la Partie 3 |

Chaque étape est validée par T4 contre son contrat : en cas d'écart, le message nomme la tâche et le champ fautif.

## P3.5 Points relevés pendant la fusion (à traiter par leurs auteurs)

1. **T1 : routage trop étroit.** Il reconnaît « CNI » et « carte nationale », mais pas « carte d'identité » seul : `Où retirer ma carte d'identité ?` est classé `hors_sujet`, sans agent, donc la réponse est un refus alors que le document contient l'information.
2. **T1 : `Bonjour` est marqué `needs_clarification: true`.** T4 répond alors « Pouvez-vous préciser votre question ? » au lieu d'un accueil.
3. **T3 : masquage des lacunes.** Avec un numéro de téléphone dans la question, le sujet de la lacune devient `... [donnée masquée]asquée], ...` : deux détections (téléphone et numéro de CNI) se recouvrent sur les mêmes chiffres et sont remplacées deux fois. Le numéro n'est pas révélé, mais le texte est abîmé. À corriger en fusionnant les zones qui se chevauchent dans `masquer` (`guardrails/sensitive.py`).
4. **T3 : seuil de score 0,35 non calibré** sur bge-m3. À régler sur les 10 vraies questions du test de bout en bout (guide, slide 8), en regardant `retrieval.top_score` dans l'audit.
5. **LLM non choisi** (P3.1) et **OCR absent** (PDF scannés), déjà signalé pour la Partie 2.

---

*Les changements faits pendant la fusion sont listés dans `NOTES_FUSION.md`.*


# Cameroun Public Service AI — Source NotebookLM
## Projet ITU AI for Good 2026 — Équipe HEMLE — Module T1 (Champy)

Ce document est conçu pour être importé dans Google NotebookLM comme source unique.
Il décrit le travail livré sur la branche `champy` : Knowledge Base (Phase 2 T1) et Orchestrateur (Phase 3 T1).

---

# 1. Présentation du projet

Cameroun Public Service AI aide les citoyens camerounais à accéder aux informations des services publics (CNI, passeport, actes, etc.).

Le système s’appuie sur une base de connaissances documentaire, puis sur un routage intelligent des questions.

Équipe : HEMLE (projet ITU AI for Good 2026).

Important : le sigle « T1 » a deux sens selon la phase.

- Phase 2 T1 = Ingestion et stockage des documents.
- Phase 3 T1 = Orchestrateur et routage des questions.

Les deux modules sont livrés sur la branche champy, sans dépendre d’un LLM pour le routage.

---

# 2. Objectifs

## Phase 2 — Knowledge Base (T1 Ingestion)

- Importer des documents PDF, DOCX, TXT.
- Vérifier extension et signature.
- Calculer une empreinte SHA-256.
- Détecter les doublons.
- Stocker le fichier dans data/raw/{domain}/{subdomain}/.
- Enregistrer les métadonnées dans SQLite.
- Exposer une API POST /documents/upload.
- Ne pas extraire le texte (réservé à T2).

## Phase 3 — Orchestrateur (T1 Routage)

- Recevoir une question citoyenne (contrat T4).
- Valider et nettoyer la question.
- Identifier l’intention.
- Identifier le domaine et le sous-domaine.
- Sélectionner 1 à 3 agents.
- Détecter si une clarification est nécessaire.
- Retourner un JSON strict de routage.
- Aucun appel à T2, T3 ou T4.
- Aucun LLM en v1 : règles + mots-clés déterministes.

---

# 3. Architecture du dépôt

```text
backend/
  knowledge_base/     # Phase 2
    collectors/       # ingestion documents
    database/         # SQLite
    api/              # FastAPI + Swagger
  orchestration/      # Phase 3
    models.py
    question_cleaner.py
    intent_classifier.py
    domain_classifier.py
    clarification_detector.py
    agent_selector.py
    orchestrator.py   # route_question()
    config.py

data/
  raw/ processed/ chunks/ indexes/ metadata/

tests/
  knowledge_base/
  orchestration/

docs/
01_CNI/               # documents sources métier
```

Technologies : Python 3.12, FastAPI (ingestion), pytest, SQLite.  
Routage Phase 3 : bibliothèque standard Python uniquement.

---

# 4. Phase 2 T1 — Ingestion (détail)

## Flux

1. Réception fichier + métadonnées (title, institution, date, domain, subdomain).
2. Vérification format : pdf, docx, txt.
3. Signature : PDF commence par %PDF ; DOCX = ZIP contenant word/document.xml.
4. Hash SHA-256 du contenu.
5. Si hash déjà connu : pas de nouvelle copie, retour de l’ID existant (is_duplicate).
6. Sinon : copie vers data/raw/... et insertion SQLite.
7. Statut : stored.

## Contrat de sortie ingestion

- document_id
- sha256
- original_filename
- stored_path
- upload_date
- domain
- institution
- status

## API

- POST /documents/upload (multipart)
- Documentation Swagger : /docs
- Health : /health

Codes HTTP utiles : 201 (créé), 200 (doublon), 400 (invalide), 415 (format non supporté).

---

# 5. Phase 3 T1 — Orchestrateur (détail)

## Point d’entrée public

Fonction : route_question(request_data)

Appelée plus tard par T4. Ne contacte pas les autres modules.

## Contrat d’entrée

- request_id (conservé tel que fourni par T4)
- question
- language
- timestamp (ISO 8601)

## Contrat de sortie (strict, 6 champs seulement)

- request_id
- intent
- domain
- subdomain
- agents
- needs_clarification

## Pipeline interne

parse_request → clean_question → classify_intent → classify_domain → select_agents → needs_clarification → JSON

## Intentions autorisées

1. accueil
2. procedure
3. juridique
4. donnees_personnelles
5. hors_sujet

Priorité si plusieurs intentions matchent :
donnees_personnelles > juridique > procedure > accueil > hors_sujet.

Si aucun mot-clé : hors_sujet.

## Domaines

Exemple principal :
- domain : public_services
- subdomain : national_identity_card | passport | birth_certificate

Si information insuffisante : domain = unknown, subdomain = unknown.
On n’invente pas un domaine.

## Clarification

needs_clarification = true pour questions vagues (« Comment faire ? », « Je veux le document. »).

needs_clarification = false pour hors sujet clair (football, recette, etc.).
Hors sujet ≠ ambigu.

## Agents

Noms indicatifs (à valider avec l’équipe T2) :
- procedure, juridique, accueil, donnees_personnelles
- 1 à 3 agents pour une intention métier
- liste vide pour hors_sujet

La configuration est centralisée dans config.py (mots-clés modifiables).

---

# 6. Exemples de routage

## Exemple A — procédure CNI

Question : Comment obtenir une carte nationale d'identité au Cameroun ?

Résultat typique :
- intent : procedure
- domain : public_services
- subdomain : national_identity_card
- agents : [procedure]
- needs_clarification : false

## Exemple B — question vague

Question : Comment faire ?

Résultat typique :
- needs_clarification : true
- domain souvent unknown

## Exemple C — hors sujet

Question : Donne-moi une recette

Résultat typique :
- intent : hors_sujet
- agents : []
- needs_clarification : false

---

# 7. Qualité et tests

Commande :

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

Résultat de référence : 152 tests passés.

Couverture Phase 3 : validation, nettoyage, 5 intentions, domaines, clarification, agents, contrat JSON, erreurs.

Couverture Phase 2 : OK, invalide, vide, doublon, métadonnées, API.

---

# 8. Installation rapide Ubuntu

```bash
cd Cameroun_publics_secvices
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest tests/orchestration -v
```

Exemple Python orchestrateur :

```python
from backend.orchestration import route_question
print(route_question({
  "request_id": "REQ-20261106-0001",
  "question": "Comment obtenir une carte nationale d'identité au Cameroun ?",
  "language": "fr",
  "timestamp": "2026-11-06T10:00:00",
}))
```

---

# 9. FAQ pour révision / oral

Q : Quelle est la différence entre les deux T1 ?
R : Phase 2 T1 ingère des documents. Phase 3 T1 route des questions.

Q : Pourquoi pas de LLM dans l’orchestrateur v1 ?
R : Pour un comportement déterministe, testable, sans coût API, conforme au guide Phase 3.

Q : Comment détecte-t-on un doublon de document ?
R : Par empreinte SHA-256 du contenu, pas par le nom de fichier.

Q : Que se passe-t-il si le domaine est inconnu ?
R : On renvoie unknown/unknown, sans inventer.

Q : Comment T4 utilise T1 Phase 3 ?
R : En appelant route_question(request_data) et en lisant le plan JSON.

Q : L’orchestrateur appelle-t-il les agents ?
R : Non. Il sélectionne seulement les noms d’agents dans le plan de routage.

Q : Où modifier les mots-clés ?
R : Dans backend/orchestration/config.py.

Q : Les documents 01_CNI sont-ils modifiés ?
R : Non. Ce sont des sources ; l’ingestion en crée une copie dans data/raw/.

---

# 10. Décisions ouvertes avec l’équipe

1. Liste définitive des noms d’agents T2.
2. Confirmation officielle de la valeur unknown pour domaine inconnu.
3. Limite de longueur de question (actuellement 1000 caractères).
4. Exposition HTTP de route_question (hors scope v1 actuelle).

---

# 11. Messages clés à retenir

- Le module Phase 3 T1 est autonome, documenté et testé.
- Le contrat de sortie est strict : six champs, pas plus.
- La classification est configurable sans changer le code métier.
- 152 tests verts constituent la preuve de non-régression actuelle.
- Le travail est prêt à être partagé avec T2 et T4 pour intégration.

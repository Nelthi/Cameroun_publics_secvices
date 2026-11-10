# Phase 3 — T1 Orchestrateur et Routage

Module responsable : **HEMLE / T1**  
Périmètre : recevoir une question citoyenne, l’analyser, produire un plan de routage.  
**Aucun LLM.** Classification par mots-clés et règles déterministes.

T1 Phase 3 **n’appelle pas** T2, T3 ni T4. T4 appellera `route_question`.

---

## 1. Installation (Ubuntu / Python 3.12)

```bash
cd Cameroun_publics_secvices
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 2. Point d’entrée public

```python
from backend.orchestration import route_question

plan = route_question({
    "request_id": "REQ-20261106-0001",
    "question": "Comment obtenir une carte nationale d'identité au Cameroun ?",
    "language": "fr",
    "timestamp": "2026-11-06T10:00:00",
})
```

## 3. Contrats

### Entrée (T4 → T1)

| Champ | Type | Règle |
|---|---|---|
| `request_id` | string | Obligatoire, conservé tel quel |
| `question` | string | Obligatoire, max 1000 caractères |
| `language` | string | Obligatoire (ex. `fr`) |
| `timestamp` | string | ISO 8601 |

Champs supplémentaires → rejet.

### Sortie (strict, 6 champs)

| Champ | Description |
|---|---|
| `request_id` | Identifiant T4 |
| `intent` | Une des 5 intentions |
| `domain` | Domaine ou `unknown` |
| `subdomain` | Sous-domaine ou `unknown` |
| `agents` | 0 à 3 noms d’agents |
| `needs_clarification` | bool |

## 4. Pipeline interne

```text
parse_request
  → clean_question
  → classify_intent
  → classify_domain
  → select_agents
  → needs_clarification
  → RoutingPlan.to_dict()
```

| Fichier | Rôle |
|---|---|
| `models.py` | Contrats + validation |
| `question_cleaner.py` | Normalisation texte / accents |
| `intent_classifier.py` | 5 intentions |
| `domain_classifier.py` | domain / subdomain |
| `clarification_detector.py` | Questions vagues |
| `agent_selector.py` | 1–3 agents |
| `orchestrator.py` | `route_question` |
| `config.py` | Mots-clés configurables |

## 5. Intentions et priorité

Intentions : `accueil`, `procedure`, `juridique`, `donnees_personnelles`, `hors_sujet`.

Si plusieurs matchent :
`donnees_personnelles` > `juridique` > `procedure` > `accueil` > `hors_sujet`.

Aucun match → `hors_sujet`.

## 6. Domaines

Config actuelle : `public_services` avec
`national_identity_card`, `passport`, `birth_certificate`.

Information insuffisante → `unknown` / `unknown` (pas d’invention).

Pour étendre : éditer `DOMAIN_KEYWORDS` dans `config.py`.

## 7. Clarification vs hors sujet

| Cas | `intent` | `needs_clarification` |
|---|---|---|
| « Comment faire ? » | souvent `procedure` | `true` |
| « Recette de cuisine » | `hors_sujet` | `false` |
| Question CNI précise | `procedure` | `false` |

## 8. Agents

Noms **indicatifs** (exemples guide) : à valider avec T2.

- Intention métier → au moins 1 agent
- Intentions secondaires matchées → jusqu’à 3 agents
- `hors_sujet` → `[]`

## 9. Tests

```bash
source .venv/bin/activate
python -m pytest tests/orchestration -v
```

Couverture : validation, nettoyage, 5 intents, domaines, clarification,
agents, contrat JSON, erreurs.

## 10. Dépannage

| Symptôme | Cause probable | Action |
|---|---|---|
| `InvalidRequestError` timestamp | Format non ISO | Utiliser `2026-11-06T10:00:00` |
| `intent=hors_sujet` à tort | Mot-clé manquant | Ajouter dans `INTENT_KEYWORDS` |
| Mauvais sous-domaine | Ambiguïté mots-clés | Affiner `DOMAIN_KEYWORDS` |
| Agents vides hors hors_sujet | Config `INTENT_TO_AGENTS` | Vérifier `config.py` |
| Import échoue | Mauvais cwd / venv | Lancer depuis la racine du repo |

## 11. Décisions ouvertes (équipe)

1. Liste définitive des agents T2
2. Confirmation de `unknown` pour domaine inconnu
3. Limite de longueur question (actuellement 1000)
4. Exposition HTTP éventuelle (hors scope v1)

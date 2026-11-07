# T3 — Guardrails et Lacunes (Phase 3)

**Cameroun Public Service AI · Phase 3 Agents, Guardrails et API · Équipe HEMLE**
 En amont : T2 (agents spécialisés) · En aval : T4 (API, audit et interface)

T3 est le dernier filtre avant que la réponse n'arrive au citoyen. Il reçoit le brouillon d'un agent
et décide : **approved** (on répond), **partial** (on répond avec ce qui est confirmé) ou
**refused** (on dit poliment qu'on ne sait pas). Ce qui manque dans la base est enregistré
comme **lacune** (*gap*), pour savoir quels documents ajouter.

```
Question ─► T1 Routage ─► T2 Agents (+ search Phase 2) ─► [ T3 Guardrails ] ─► T4 Réponse + journal
```

T3 n'appelle ni LLM ni `search()` : ce sont des contrôles déterministes, rapides et explicables.

## Entrée

Le brouillon de T2 + la question d'origine. En plus, **les passages renvoyés par `search()`**
(voir « Points à convenir avec T2 »).

```json
{
  "question": "Quelles pièces pour faire ma CNI ?",
  "draft": {
    "request_id": "REQ-20261106-0001",
    "agent": "procedure",
    "answer_draft": "Pour la CNI, il faut un acte de naissance [1]. ...",
    "citations": [{"chunk_id": "DOC-...-C001", "document_id": "DOC-...", "source_page": 1}],
    "retrieval": {"top_score": 0.71, "n_chunks": 4}
  },
  "passages": [{"chunk_id": "DOC-...-C001", "text": "..."}]
}
```

## Sortie (contrat de la slide 6)

```json
{
  "request_id": "REQ-20261106-0001",
  "status": "approved",
  "final_answer": "...",
  "citations": [{"chunk_id": "...", "document_id": "...", "source_page": 1}],
  "checks": {"grounded": true, "has_citations": true, "score_ok": true, "no_sensitive_data": true},
  "gaps": [{"topic": "frais CNI", "reason": "no_relevant_chunk"}]
}
```

`citations` ne contient que les sources réellement utilisées dans `final_answer`.

## Les contrôles

| Contrôle (`checks`) | Ce qui est vérifié | Si échec |
|---|---|---|
| `score_ok` | `top_score` ≥ seuil (0,35 par défaut) et au moins un passage | `refused`, lacune `low_score` ou `no_relevant_chunk` |
| `has_citations` | chaque affirmation (phrase d'au moins 4 mots) porte un marqueur `[n]` | la phrase est retirée, lacune `no_citation` |
| `grounded` | `[n]` existe dans `citations` et dans les passages ; chiffres et mots clés de la phrase retrouvés dans le passage cité | la phrase est retirée, lacune `invalid_citation` ou `unsupported_claim` |
| `no_sensitive_data` | pas de numéro de CNI, de téléphone ou d'e-mail dans la question ni dans le brouillon | donnée masquée (`[donnée masquée]`) et avertissement |

**Décision du statut :**
- `refused` : score trop bas, brouillon du type « je ne sais pas », ou plus aucune phrase vérifiée après nettoyage.
- `partial` : au moins une phrase vérifiée, mais d'autres ont été retirées ou une donnée sensible a été masquée.
- `approved` : tout est vérifié, aucune donnée sensible.

Les numéros qui figurent dans les **documents officiels cités** (ex. numéro d'information d'une institution)
sont considérés comme publics et laissés. Ceux de la question ne le sont jamais.
Les sujets des lacunes sont aussi masqués : aucune donnée personnelle n'arrive dans la table `gaps`.

## Utilisation

Python 3.9 ou plus, aucune dépendance externe. À lancer depuis ce dossier (`t3_guardrails/`).

```bash
# vérifier un fichier (un objet ou une liste d'objets) -> data/validated/{request_id}.json
python -m guardrails examples/brouillons_t2_exemples.json

# autre dossier ou autre seuil
python -m guardrails mon_fichier.json --out-dir ../data/validated --seuil 0.40
```

Sous Windows, utilisez `python` ou `py` si `python3` n'est pas reconnu.
Pour T4, utilisation directe en Python :

```python
from guardrails import verifier_brouillon
reponse = verifier_brouillon(draft_t2, question, passages)
```

## Les 6 brouillons de test (`examples/`)

Données **inventées**, au format de la Phase 2. Les sorties attendues sont dans `sorties_t3_attendues.json`.

| Requête | Cas | Résultat attendu |
|---|---|---|
| `REQ-MOCK-0001` | bon brouillon, cité et fondé | `approved` |
| `REQ-MOCK-0002` | aucune citation | `refused`, lacunes `no_citation` |
| `REQ-MOCK-0003` | score trop bas (0,21) | `refused`, lacune `low_score` |
| `REQ-MOCK-0004` | numéro de téléphone dans la question et le brouillon | `partial`, numéro non repris |
| `REQ-MOCK-0005` | hors sujet (football) | `refused`, lacune `no_relevant_chunk` |
| `REQ-MOCK-0006` | un chiffre inventé (48 heures) absent des passages | `partial`, phrase retirée |

## Structure

```
t3_guardrails/
├── README.md
├── guardrails/
│   ├── core.py        # verifier_brouillon : tous les contrôles et le statut
│   ├── sensitive.py   # détection et masquage des données sensibles
│   ├── cli.py         # run() : lit un fichier, écrit data/validated/
│   └── __main__.py    # python -m guardrails
├── examples/
└── data/validated/    # sorties générées (ignorées par git)
```

## Points à convenir avec T2 et T4 (avant l'intégration)

1. **Passages dans la sortie de T2.** Le contrat de T2 ne contient pas le texte des passages, or T3 doit
   vérifier que les citations existent « vraiment dans les passages ». Demander à T2 d'ajouter `passages`
   (`chunk_id` + `text`). Sans cela, T3 ne peut contrôler ni l'existence des citations ni le contenu :
   un avertissement s'affiche et seul le contrôle de présence des `[n]` reste actif.
2. **Correspondance `[n]` ↔ citations.** Hypothèse : `[1]` est la 1re entrée de `citations`, `[2]` la 2e, etc.
   Si T2 ne garde dans `citations` que les passages utilisés, la numérotation du prompt peut ne plus
   correspondre. Soit T2 renvoie toutes les citations dans l'ordre du prompt, soit chaque citation reçoit un champ `ref`.
3. **Sens de `top_score`.** Le seuil suppose « plus grand = meilleur » (0,71 dans la slide). FAISS `IndexFlatL2`
   renvoie une **distance** (plus petit = meilleur) : T2/T4 doivent la convertir en similarité avant.
4. **Calibrer le seuil.** 0,35 est un exemple de la slide. À régler sur les 10 vraies questions du test de bout en bout.
5. **Journal d'audit (T4).** La question brute peut contenir un numéro de CNI : T4 doit la masquer avant
   de l'écrire dans `audit_log` (la fonction `masquer` de `guardrails/sensitive.py` peut être réutilisée).

## Limites connues

- Le contrôle de fond est lexical (chiffres et mots clés), pas sémantique : il attrape les chiffres inventés et
  les phrases sans rapport, pas une reformulation subtilement fausse.
- Les formats de numéro de CNI et de téléphone sont des hypothèses (téléphone à 9 chiffres commençant par 6 ou 2,
  CNI de 8 à 12 chiffres après le mot « CNI » ou « numéro »). À confirmer sur de vrais exemples.
- Les abréviations rares peuvent encore couper une phrase trop tôt.
- Le statut « hors sujet » n'utilise pas l'intention de T1 (absente de l'entrée) : il vient du score et du brouillon.

]

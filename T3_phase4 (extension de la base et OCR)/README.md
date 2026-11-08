# T3 — Extension de la base et OCR (Phase 4)

**Cameroun Public Service AI · Phase 4 Évaluation, Lacunes et Livraison · Équipe HEMLE**
· En amont : T2 (`gap_report.json`) · En aval : T1 (nouvelle évaluation avant/après) et T4 (page Qualité, pitch)

T3 comble les lacunes repérées par T2  al aphase 3: il ajoute de nouveaux documents officiels à la base, lit les
**PDF scannés par OCR (Tesseract)**, fait passer chaque document dans la chaîne de la Phase 2
(ingestion → extraction → découpage), reconstruit l'index et écrit le bilan `kb_update.json`.

```
T2 gap_report.json ─► [ T3 : collecte → OCR/extraction → découpage → build_index ] ─► kb_update.json
                                                                                       │
                              T1 relance l'évaluation (avant / après) ◄────────────────┘
```

Règle de la slide 3 : T3 ne modifie que son dossier `kb_update/`. Le code des Phases 2 et 3 est **appelé**, pas modifié.
La seule exception convenue : l'OCR s'ajoute à l'extraction de la Phase 2 (voir « Brancher l'OCR »).

## Entrées

1. **`data/reports/gap_report.json`** (T2) : les sujets à combler. T3 traite d'abord les lacunes les plus fréquentes.
2. **Un manifeste des nouveaux documents** que vous avez collectés (`kb_update/new_documents.json`) :

```json
[
  {"path": "documents/bareme_frais.pdf", "title": "Barème des frais",
   "institution": "DGSN", "domain": "public_services", "subdomain": "national_identity_card",
   "date": "2026-11-10", "source_url": "https://...", "gap_ids": ["GAP-001"]}
]
```

`path` est relatif au dossier du manifeste. `gap_ids` dit quelles lacunes le document comble.
Le manifeste sert aussi de **registre des sources** (institution, date, lien) : notez-les à la collecte.

## Sorties

`data/reports/kb_update.json` (contrat de la slide 6) :

```json
{
  "update_date": "2026-11-13T09:00:00",
  "gaps_addressed": ["GAP-001"],
  "documents_added": [{"document_id": "DOC-...", "institution": "...", "ocr_used": true}],
  "index": {"n_chunks_before": 120, "n_chunks_after": 168, "dim": 1024},
  "status": "indexed"
}
```

| Champ | Signification |
|---|---|
| `gaps_addressed` | lacunes visées par au moins un document ajouté avec succès (ids connus de `gap_report.json`) |
| `documents_added` | un élément par document réellement ajouté ; `ocr_used` vaut `true` si au moins une page a été lue par OCR |
| `index` | nombre de fragments avant/après et dimension des vecteurs, lus sur la vraie base |
| `status` | `indexed` (au moins un document ajouté et index reconstruit) ou `no_change` (rien de nouveau, par exemple tout en doublon) |

À côté, `data/reports/kb_update_details.json` (hors contrat) garde le détail : titre, lien source, pages, fragments,
**avertissements d'extraction** (OCR peu fiable, page vide) et les documents ignorés avec la raison (doublon, fichier introuvable…).
Un document en échec n'arrête pas les autres.

## L'OCR

Une page est lue par OCR quand son texte natif fait moins de 30 caractères (c'est un scan). Les autres pages gardent
leur texte natif : un même PDF peut mélanger les deux. Étapes : page rendue en image (300 dpi, niveaux de gris),
Tesseract en français, puis le même nettoyage que T2 (espaces, sauts de ligne, mots coupés en fin de ligne).
Si la confiance moyenne d'une page est sous 60/100, un avertissement est ajouté : **relisez ces textes à la main**,
un OCR médiocre dégrade la recherche sans que personne ne le voie.

Installation de Tesseract (programme à part, en plus de `pip install -r requirements.txt`) :
- Ubuntu/Debian : `sudo apt install tesseract-ocr tesseract-ocr-fra`
- macOS : `brew install tesseract tesseract-lang`
- Windows : installeur « UB Mannheim », puis variable d'environnement `TESSERACT_CMD` vers `tesseract.exe`

Réglages facultatifs : variables `OCR_LANG` (défaut `fra`) et `OCR_DPI` (défaut `300`).

### Brancher l'OCR dans l'extraction de la Phase 2

Dans la boucle sur les pages d'un PDF, à l'endroit où l'on ajoutait un *warning* pour un texte vide :

```python
from kb_update.ocr import needs_ocr, ocr_pdf_page
texte = page.get_text()
if needs_ocr(texte):
    texte, confiance = ocr_pdf_page(page)
    ocr_used = True
```

À convenir avec le propriétaire du code d'extraction avant de le toucher.

## Utilisation

À lancer depuis la **racine du dépôt** (le dossier qui contient `kb_update/`), avec le module de découpage de la Phase 2
(`t3_chunking`) sur le `PYTHONPATH`.

```bash
# 1. quelles lacunes traiter d'abord ?
python -m kb_update.run_update --documents kb_update/new_documents.json --priorites

# 2. lancer la mise à jour avec le vrai code de la Phase 2
python -m kb_update.run_update --documents kb_update/new_documents.json --hooks kb_update.phase2_hooks
```

Un avertissement signale les lacunes qu'aucun document du manifeste ne vise.

### Essai sans la Phase 2 (démonstration)

```bash
PYTHONPATH=../t3_chunking:.. python -m kb_update.run_update \
  --documents examples/new_documents_exemple.json --gap-report examples/gap_report_exemple.json \
  --out out/kb_update.json
```

Le mode par défaut (`hooks_demo.py`) copie les fichiers dans `demo_store/`, compte les fragments et n'indexe rien
(`dim` vaut `null`). `examples/` contient un faux `gap_report.json`, un manifeste, trois documents de test (un PDF scanné,
un PDF texte, un TXT, **inventés**) et le `kb_update_exemple.json` obtenu. Relancer deux fois montre la détection des doublons.

### Brancher le vrai code de la Phase 2

Créer `kb_update/phase2_hooks.py` avec une fonction `get_hooks()` qui renvoie un objet `Hooks` (voir `pipeline.py`) :

```python
from chunking import chunk_document
from kb_update.pipeline import Hooks
from kb_update.ocr import extract_document          # ou la fonction d'extraction de la Phase 2, une fois l'OCR branché

def get_hooks():
    return Hooks(
        ingest=...,        # fonction d'ingestion de la Phase 2 : (chemin, meta) -> {document_id, stored_path, status}
        extract=extract_document,
        chunk=chunk_document,
        index_stats=...,   # lit le nombre de fragments et la dimension de l'index actuel
        build_index=...,   # appelle build_index puis renvoie {n_chunks, dim}
        data_dir="data",
    )
```

Les `...` dépendent du code des autres membres : il faut les noms exacts de leurs fonctions (voir plus bas).

## Structure

```
T3_phase4 (extension de la base et OCR)/
├── README.md
├── requirements.txt
├── ocr.py             # Tesseract + extraction d'un document au format T2 (PDF, DOCX, TXT)
├── priorities.py      # lecture de gap_report.json, ordre de priorité, lacunes non couvertes
├── pipeline.py        # Hooks + run() : traite les documents et écrit kb_update.json
├── hooks_demo.py      # branchements de démonstration (sans vraie Phase 2)
├── run_update.py      # python -m kb_update.run_update
└── examples/
```

## Points à convenir avec les autres

1. **Noms des fonctions de la Phase 2** : ingestion (T1), extraction (T2), `build_index` (T4) et lecture de l'état de l'index.
   Sans eux, `phase2_hooks.py` ne peut pas être écrit.
2. **`dim: 1024`** dans l'exemple de la slide ne correspond pas à `all-MiniLM-L6-v2` (384). Si l'équipe a changé de modèle
   d'embedding (un modèle multilingue convient mieux au français), la valeur doit être lue sur l'index, jamais écrite à la main.
3. **`build_index` doit reconstruire à partir de tous les fichiers `data/chunks/`** (anciens et nouveaux) et garder des
   `chunk_id` stables, sinon les citations de la Phase 3 se décalent.
4. **Le seuil de score des guardrails (Phase 3)** a été fixé sur l'ancienne base : à revérifier après la mise à jour.
5. **Machine propre pour la démo (T4)** : Tesseract est un programme système à installer (`apt install tesseract-ocr tesseract-ocr-fra`
   dans `start.sh` ou le Dockerfile), `pip` ne suffit pas.
6. **Qui collecte les documents** ? Le planning répartissait la collecte autrement que les phases : à confirmer.

## Limites connues

- L'OCR lit mal les scans de mauvaise qualité, tamponnés ou photographiés de travers : les avertissements de confiance aident, pas plus.
- Les tableaux scannés sont lus ligne à ligne, sans structure. Un DOCX composé uniquement d'images n'est pas traité par OCR.
- Les documents sont détectés en doublon par leur contenu (SHA-256) dans la démonstration ; en réel, c'est le comportement de l'ingestion de la Phase 2.
- Le mode démonstration n'a calculé aucun vecteur : seule la mise à jour réelle valide `index.dim` et le temps de reconstruction.

## Liste de contrôle avant livraison

- [ ] `kb_update.json` respecte le contrat de la slide 6 et `gaps_addressed` n'est pas vide
- [ ] Chaque document ajouté a son institution, sa date et son lien dans le manifeste
- [ ] Les avertissements d'OCR de `kb_update_details.json` ont été relus
- [ ] `n_chunks_after` est supérieur à `n_chunks_before`
- [ ] T1 prévenu pour relancer l'évaluation, T4 pour la page Qualité

# T3 — Découpage (Chunking)

**Cameroun Public Service AI · Phase 2 Base de connaissances · Équipe HEMLE**
Responsable : Alex · En amont : T2 (extraction et nettoyage) · En aval : T4 (vectorisation et index FAISS)

T3 découpe le texte nettoyé d'un document en petits fragments (*chunks*) qui se chevauchent.
Chaque fragment deviendra un vecteur dans l'index FAISS : la recherche pourra ainsi renvoyer
un passage précis et sa page d'origine, plutôt qu'un document entier.

```
T1 Ingestion ──► T2 Extraction ──► [ T3 Découpage ] ──► T4 Vectorisation + FAISS
                  data/processed/     data/chunks/          data/indexes/
```

T3 ne lit ni SQLite, ni les fichiers PDF/DOCX d'origine, et ne calcule aucun vecteur.
Seuls les contrats JSON ci-dessous comptent.

## Entrée (produite par T2)

Un fichier JSON rangé dans `data/processed/{domain}/{subdomain}/`. Seuls deux champs sont utilisés :

```json
{
  "document_id": "DOC-A1B2C3D4",
  "pages": [
    {"page_number": 1, "text": "..."},
    {"page_number": 2, "text": "..."}
  ]
}
```

Les autres champs de T2 (`full_text`, `warnings`, `status`, `extraction_date`) sont ignorés.
Les pages vides sont sautées et les pages sont triées par `page_number`.

## Sortie (consommée par T4)

Un fichier par document : `data/chunks/{document_id}.json`

```json
{
  "document_id": "DOC-A1B2C3D4",
  "chunk_size": 800,
  "chunk_overlap": 120,
  "chunks": [
    {
      "chunk_id": "DOC-A1B2C3D4-C001",
      "text": "...",
      "source_page": 1,
      "position": 0
    }
  ]
}
```

| Champ | Signification |
|---|---|
| `document_id` | Document d'origine (repris de T2). |
| `chunk_size` / `chunk_overlap` | Paramètres utilisés (800 / 120 caractères). |
| `chunk_id` | Identifiant unique : `{document_id}-C001`, `C002`… |
| `text` | Texte du fragment, 800 caractères maximum. |
| `source_page` | Page où le fragment **commence**. |
| `position` | Rang du fragment dans le document, à partir de 0. |

Les noms de champs sont en `snake_case`, comme convenu pour toute l'équipe. Un document sans texte
exploitable produit un fichier valide avec `"chunks": []`.

## Règles de découpage

- Fragments de **800 caractères** maximum, avec **120 caractères de chevauchement** entre deux fragments
  consécutifs : une règle coupée à la frontière apparaît entière dans l'un des deux.
- Coupure sur une fin de phrase (`.` `;` `!` `?`) si possible, sinon sur un espace. Les coupures dans la
  première moitié de la fenêtre sont ignorées pour éviter des fragments minuscules.
- Jamais de fragment qui commence ou finit au milieu d'un mot (seule exception : un mot unique de plus de 800 caractères).
- Un fragment à cheval sur deux pages reçoit la page où il commence.

## Utilisation

Python 3.9 ou plus, aucune dépendance externe. À lancer depuis ce dossier (`t3_chunking/`).

```bash
# découper un fichier T2 -> data/chunks/{document_id}.json
python -m chunking chemin/vers/sortie_t2.json

# écrire ailleurs (par exemple le dossier data/ partagé du dépôt)
python -m chunking chemin/vers/sortie_t2.json --out-dir ../data/chunks

# vérifier qu'un fichier de sortie respecte le contrat (avant de prévenir T4)
python -m chunking.validate data/chunks/DOC-A1B2C3D4.json
```


## Exemples

- `examples/input_t2_example.json` : faux fichier T2 pour travailler sans attendre T2.
- `examples/output_t3_example.json` : sortie T3 correspondante.

```bash
python -m chunking examples/input_t2_example.json --out-dir sortie_test
```

## Structure

```
t3_chunking/
├── README.md
├── chunking/
│   ├── core.py        # algorithme de découpage
│   ├── contract.py    # vérification du contrat (liste d'erreurs)
│   ├── cli.py         # run() : lit le JSON T2, écrit data/chunks/
│   ├── validate.py    # python -m chunking.validate
│   └── __main__.py    # python -m chunking
├── examples/
└── data/chunks/       # sorties générées (ignorées par git, .gitkeep conservé)
```


## Limites connues

- Seule la page de début est conservée. Si l'interface doit citer « pages 2 à 3 », il faudra ajouter un champ
  `source_page_end` au contrat (à convenir avec T4).
- Une abréviation comme « art. 5. » peut provoquer une coupure trop tôt.
- La qualité dépend de T2 : un PDF scanné (texte vide) donne zéro fragment.
- Les tailles sont en caractères, pas en tokens. 800 caractères de français restent bien sous la limite
  de 256 tokens des modèles de type MiniLM.

# Assistant Services Publics — application web (React + Vite + TypeScript)

Mêmes deux espaces que l'application mobile :

- **Citoyen** : panneau de discussions à gauche, messages, zone de saisie avec boutons **voix** et **pièce jointe** (interface seulement pour l'instant), réponses sourcées (document et page).
- **Administrateur** : envoi de **plusieurs documents** par **glisser-déposer** (fichiers ou dossier), **copier-coller** (`Ctrl+V`) ou parcours ; Groq propose automatiquement titre, institution, date et sous-domaine ; boutons pour chaque phase (extraction, découpage **code natif / agent IA**, vectorisation) ; consultation des données (texte, fragments, vecteurs, journal RAG et lacunes).

## Lancer

Prérequis : Node.js 20 ou plus.

```bash
npm install
npm run dev        # http://localhost:5173
```

Construire pour la production : `npm run build` (dossier `dist/`).

## Relier l'application à l'API

1. Lancer l'API du projet fusionné : `python -m backend.server --demo-llm`.
2. Dans l'application : engrenage de la page d'accueil → **Adresse de l'API** (par défaut `http://localhost:8000`, ou `VITE_API_URL`) → **Tester la connexion**.
   Si `ADMIN_TOKEN` est défini sur le serveur, le saisir aussi.

L'API autorise les appels depuis n'importe quelle origine (CORS) : l'application peut être ouverte depuis un autre appareil du réseau avec `npm run dev` (l'option `--host` est activée).

## Structure

```
src/App.tsx, pages/RolePage.tsx   choix de l'espace, paramètres
src/pages/UserApp.tsx             espace citoyen
src/pages/Admin*.tsx              espace administrateur
src/api.ts                        client de l'API
src/styles.css                    style
```

Vérifications faites : `npm run build` (TypeScript et Vite) sans erreur. Rendu visuel non contrôlé dans un navigateur dans cet environnement.

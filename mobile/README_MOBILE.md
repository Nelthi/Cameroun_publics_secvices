# Assistant Services Publics — application mobile (React Native / Expo)

Deux espaces dans la même application :

- **Citoyen** : panneau de discussions à gauche (bouton menu), zone de messages, zone de saisie avec boutons **voix** et **pièce jointe** (interface seulement pour l'instant), réponses avec leurs **sources** (document et page).
- **Administrateur** : envoi de **plusieurs documents** (Groq propose titre, institution, date et sous-domaine), lancement de chaque phase par bouton (extraction, découpage **code natif / agent IA**, vectorisation), consultation des données (texte extrait, fragments, vecteurs, journal RAG et lacunes).

## Lancer

Prérequis : Node.js 20 ou plus, et l'application **Expo Go** sur le téléphone (Android ou iOS).

```bash
npm install
npx expo start
```

Scanner le QR code avec Expo Go (téléphone et ordinateur sur le **même Wi-Fi**).

## Relier l'application à l'API

1. Lancer l'API du projet fusionné : `python -m backend.server --demo-llm` (écoute sur `0.0.0.0:8000`).
2. Dans l'application : engrenage de l'écran d'accueil → **Adresse de l'API** → `http://<IP de la machine>:8000`, puis **Tester**.
   - Téléphone réel : l'IP de la machine qui lance l'API (`ip a`). Avec VirtualBox, passer la carte réseau en **accès par pont**.
   - Émulateur Android : `http://10.0.2.2:8000`.
   - Si `ADMIN_TOKEN` est défini sur le serveur, le saisir aussi dans les paramètres.

## Structure

```
App.tsx                      choix de l'espace, paramètres
src/api.ts                   client de l'API (JSON et envoi de fichiers)
src/screens/UserChat.tsx     espace citoyen
src/screens/Admin*.tsx       espace administrateur (accueil, documents, traitements, données)
src/components/ui.tsx        composants (boutons, cartes, badges, notifications)
src/theme.ts                 couleurs et styles
```

Vérifications faites : `npx tsc --noEmit` sans erreur et `npx expo export --platform android` (bundle Hermes généré). Non testé sur un appareil réel.

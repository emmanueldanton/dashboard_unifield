<!--
  SYNC IMPACT REPORT
  Version change: [UNVERSIONED / blank template] → 1.0.0
  Modified principles: None — initial population from blank template
  Added sections:
    - Core Principles I through IX (all new)
    - Gouvernance Technique
    - Conformité et Sécurité (ISO 27001:2022)
    - Governance (versioning, amendment procedure, compliance review)
  Removed sections: All placeholder tokens replaced; no content removed
  Templates requiring updates:
    ✅ .specify/memory/constitution.md — written (this file)
    ✅ .specify/templates/plan-template.md — Constitution Check gate wording unchanged;
       gates will be derived from this constitution at plan-time. No structural change needed.
    ✅ .specify/templates/spec-template.md — FR/SC structure aligns with principle-driven
       requirements (auth, cache, secrets, ISO). No structural change needed.
    ✅ .specify/templates/tasks-template.md — Phase 2 Foundational tasks map naturally to
       auth setup, MongoClient singleton, cache layer, secrets config. No structural change needed.
  Deferred TODOs:
    - TODO(RATIFICATION_DATE): Confirm exact first-adoption date if different from 2026-05-26.
-->

# Dashboard UNIFIELD CAD.42 Constitution

## Core Principles

### I. Proportionnalité

Le dashboard est dimensionné pour **CAD.42 Services SAS — 8 personnes**, CTO = RSSI inclus.
Toute décision d'architecture, de gouvernance ou de procédure DOIT rester applicable sans DSI
dédiée et sans dépasser 3 niveaux d'approbation. Les abstractions, outillages et processus
superflus sont interdits.

Toute proposition introduisant une couche, un service ou une procédure qui présupposerait une
équipe dédiée ou plus de 3 signataires DOIT être rejetée ou amendée avant merge.

**Rationale**: Une organisation de 8 personnes ne peut pas entretenir des couches d'infrastructure
conçues pour des équipes de 80. La complexité inutile est elle-même un risque SMSI.

### II. Authentification déléguée — auth-api / Microsoft Entra ID

L'authentification est entièrement déléguée à **auth-api** (ServiceConsumer) via le flow
Microsoft Authorization Code. Le slug applicatif est immuable : `"unifield"`. Le secret est
exclusivement géré en variable d'environnement.

Règles MUST :
- Le rôle DOIT être vérifié **avant** toute création de session.
- Tout utilisateur sans rôle `admin` ni `app:unifield:{admin,write,read}` DOIT recevoir un
  **403 explicite**, sans session créée et sans redirection vers une page d'accueil.
- Le cookie de session DOIT être nommé `unifield.sid` avec les attributs `httpOnly`,
  `SameSite=Lax` et `Secure` (HTTPS uniquement).
- Le store RAM de sessions DOIT hacher les identifiants de session en **SHA-256**.
- Le header `X-User-Email` est **interdit en production**.
- Le bypass développement (`UNIFIELD_DEV_AUTH_BYPASS=true`) est exclusif à l'environnement
  local ; il ne DOIT PAS être présent ou activable dans le code de production déployé.
- Aucun formulaire email/clé n'existe en production ni dans aucune branche mergée en main.

### III. Source de données MongoDB Atlas — lecture seule sur collections métier

Le dashboard consomme MongoDB Atlas en **lecture seule** sur les collections métier :
`projects`, `trackers`, `units`, `events`, `schedule`, `scores`.

Les seules écritures autorisées depuis l'application ciblent les collections dédiées
`snapshots` et `alert_history`. Aucune écriture ne DOIT cibler une collection métier
depuis le dashboard ou ses callbacks.

**Rationale**: Séparation des responsabilités — `alerter.py` est le seul processus qui
produit de la donnée métier ; le dashboard est un consommateur en lecture.

### IV. Cache serveur obligatoire — chargement en 2 temps

Aucun callback Dash ne DOIT émettre de requête MongoDB directe. Toute donnée accessible
depuis les callbacks transite exclusivement par le cache serveur.

Protocole de chargement en 2 temps :
1. **Vue légère** : collections `projects` + `trackers` pour tous les projets.
2. **Détail** : collections `units`, `events`, `schedule`, `scores` pour les **projets
   actifs uniquement**.

Contraintes techniques MUST :
- `MongoClient` DOIT être un singleton partagé ; jamais réinstancié par requête ou par callback.
- L'association tracker → projet DOIT être réalisée en Python. L'opérateur `$lookup` est interdit.
- En cas d'échec MongoDB : dégradation gracieuse obligatoire, cache existant conservé,
  l'application ne DOIT PAS crasher.

### V. Iso-interface — préservation des structures consommées par `business/`

Le loader MongoDB DOIT reproduire **exactement** les structures de données attendues par le
module `business/`, notamment :
- `lastTrack.message.battery_volt`
- `lastUpdate`
- `schedule` (jours / slots)
- Enrichissements : `_is_connected`, `_battery_volt`, et tous les champs enrichis existants.

Les modules `business/` (`trackers.py`, `flags.py`, `schedule.py`, `segments.py`, `alerts.py`)
et `ui/tabs/` NE SONT PAS modifiés dans leur logique lors de la migration. Ce sont des fonctions
pures préservées telles quelles. Toute modification de ces modules constitue une violation de
ce principe.

**Rationale**: Garantit que la migration de source de données (REST → MongoDB) est transparente
pour les couches métier et UI, et que la régression fonctionnelle est détectable immédiatement.

### VI. Layout SMSI — Charte visuelle Z42

En production, le layout DOIT être un **header horizontal fixe** contenant dans l'ordre :
titre de l'application, métadonnées de session, statut de connexion MongoDB, bouton Actualiser,
KPIs globaux, et 4 onglets de navigation SMSI.

Aucune sidebar ne DOIT être présente en production.

La charte visuelle DOIT respecter le portail Z42 : couleur d'accent `#7DC242`, fond `#0a0a0a`,
thème dark cyber. Toute déviation visuelle nécessite un amendement de la présente constitution.

### VII. Séparation des processus data

`alerter.py` est le **seul processus** habilité à écrire dans MongoDB (collections `snapshots`
et `alert_history`). Il s'exécute séparément sous PM2 ou systemd, indépendamment du processus
Gunicorn du dashboard.

Le dashboard ne DOIT contenir aucune logique d'écriture sur données métier ni aucune logique
d'envoi d'alertes initié depuis un callback Dash.

### VIII. Secrets hors du code

Les secrets suivants sont **exclusivement** gérés en variables d'environnement. Ils ne DOIVENT
jamais être commités, jamais loggés, et jamais interpolés dans des chaînes de log ou de trace :
- `UNIFIELD_MONGO_URI`
- `AUTH_API_SERVICE_CONSUMER_SECRET`
- `MAILGUN_API_KEY`
- `MAILGUN_WEBHOOK_SIGNING_KEY`

Tout commit contenant l'une de ces valeurs en clair constitue une **violation de sécurité**
et DOIT être traité comme un incident SMSI (rotation immédiate du secret concerné).

### IX. Stack minimal

La stack autorisée est strictement : **Dash, Plotly, pymongo, requests, python-dotenv,
gunicorn**. Aucun ORM, aucun framework web supplémentaire ne PEUT être introduit sans
amendement formel de cette constitution. Chaque nouvelle dépendance DOIT être justifiée
par une nécessité fonctionnelle documentée dans le PR d'introduction.

## Gouvernance Technique

Les règles suivantes régissent l'architecture interne et sont non-négociables :

**Séparation des couches** — Aucun module n'importe depuis une couche non-adjacente.
L'ordre strict est `api/` → `business/` → `ui/` → `callbacks/`. Toute violation entraîne
un refus de merge sans exception.

**Mapping des rôles isolé** — La correspondance entre rôles auth-api et rôles internes
est exclusivement définie dans `auth/role_check.py`. Aucun autre module ne DOIT contenir
cette logique.

**Source de vérité UI** — `dcc.Store` est la seule source de vérité pour la navigation,
les filtres et les sélections. Les callbacks ne DOIVENT pas maintenir d'état local.

**Gestion d'erreur systématique** — Toute opération MongoDB DOIT être encapsulée dans un
gestionnaire d'erreur. L'application ne DOIT jamais crasher suite à une erreur MongoDB ;
elle dégrade gracieusement en conservant le cache existant.

**Logs structurés** — Les événements suivants DOIVENT être loggés avec horodatage ISO 8601 :
refresh de cache, échec MongoDB, login, logout, envoi d'alerte, réception de webhook Mailgun.
Aucun secret ne DOIT apparaître dans les logs sous aucune forme (valeur, extrait, hash).

**MongoClient singleton** — Une seule instance de `MongoClient` par processus Gunicorn,
réutilisée sur toutes les requêtes et tous les callbacks.

## Conformité et Sécurité

Le dashboard est soumis aux contrôles ISO 27001:2022 suivants, vérifiables à chaque PR :

- **A.5.15 — Contrôle d'accès** : rôles vérifiés avant toute session, 403 explicite pour
  les utilisateurs non autorisés (principe II).
- **A.5.18 — Droits d'accès** : lecture seule sur collections métier, écriture limitée aux
  collections `snapshots` / `alert_history` (principes III, VII).
- **A.8.5 — Authentification sécurisée** : Microsoft Entra ID via auth-api, cookie httpOnly
  SameSite=Lax, SHA-256 store (principe II).
- **A.8.15 — Journalisation** : logs structurés horodatés, aucun secret en log (gouvernance
  technique + principe VIII).
- **A.8.16 — Surveillance** : dashboard en lecture seule, `alerter.py` seul producteur de
  données d'alerte (principe VII).

**Déploiement cible** : VM Ubuntu, reverse proxy nginx partagé, préfixe `/unifield/`,
serveur applicatif Gunicorn.

## Governance

**Autorité** : Cette constitution prime sur toute pratique de développement antérieure ou
tout document technique non explicitement listé comme exception.

**Procédure d'amendement** :
1. Proposer l'amendement via un PR avec justification explicite référençant le principe visé.
2. Approbation par le CTO/RSSI (niveau d'approbation unique pour CAD.42 — principe I).
3. Mettre à jour ce fichier : incrémenter la version, mettre à jour `Last Amended`.
4. Propager les impacts aux templates dépendants (`plan-template.md`, `spec-template.md`,
   `tasks-template.md`) si des sections structurelles changent.

**Politique de version** :
- **MAJOR** : suppression ou redéfinition incompatible d'un principe existant.
- **MINOR** : ajout d'un nouveau principe ou extension matérielle d'une section.
- **PATCH** : clarification, reformulation, correction orthographique ou typographique.

**Revue de conformité** : À chaque merge en branche `main`, le reviewer DOIT vérifier la
conformité aux principes I à IX. Aucun PR ne PEUT être mergé si un principe est violé sans
amendement préalable et approuvé de la présente constitution.

**Version**: 1.0.0 | **Ratified**: 2026-05-26 | **Last Amended**: 2026-05-26

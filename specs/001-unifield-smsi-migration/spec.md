# Feature Specification: Migration UNIFIELD — Console SMSI CAD.42

**Feature Branch**: `001-unifield-smsi-migration`
**Created**: 2026-05-26
**Status**: Clarified
**Input**: User description: "Migrer le Dashboard UNIFIELD existant pour qu'il devienne la 5ᵉ console
du monorepo SMSI, en remplaçant sa source de données (REST → MongoDB), son authentification
(formulaire → SSO), et son layout (sidebar + 5 onglets → header SMSI + 4 onglets), sans régression
sur la logique métier."

## Clarifications

### Session 2026-05-26

- Q: Iso-interface — mécanisme de validation du loader Mongo ? → A: Validation par diff contre un
  jeu de référence figé depuis le loader REST. Tout écart de champ ou d'enrichissement `_*` est un
  bug de mapping à corriger dans `api/mongo_loader.py`, jamais dans `business/`.
- Q: Couche d'adaptation des champs — qui réécrit si MongoDB stocke battery à plat ? → A: Le loader
  Mongo (`api/mongo_loader.py`) réécrit vers la forme attendue par `business/`. On ne touche jamais
  `business/trackers.py`.
- Q: MongoClient singleton — mode de création et paramètres de pool ? → A: Création lazy au premier
  accès par worker (jamais au niveau module). Paramètres : `maxPoolSize=20`, `minPoolSize=3`,
  `connectTimeoutMS=10000`, `socketTimeoutMS=15000`, `maxIdleTimeMS=60000`.
- Q: Cache singleton — que devient la clé `md5(email:key)` ? → A: La clé disparaît. Les signatures
  `get_cached_data(email, key)` sont conservées mais ignorent les arguments en interne (clé fixe
  unique par process).
- Q: Onglets — comment est géré l'état actif ? → A: Le store `active-tab` est la seule source de
  vérité. La classe CSS active est calculée depuis ce store, jamais depuis `n_clicks` direct. Un seul
  callback gère la mise à jour de `active-tab` (reçoit les 4 `n_clicks`, émet la nouvelle valeur).
  Valeur par défaut : `"dashboard"`.
- Q: Graphe évolution — quand le callback dédié se déclenche-t-il ? → A: Ce callback écoute
  uniquement le projet sélectionné et la plage temporelle. Il ne se déclenche pas à chaque refresh
  15 min sauf si de nouveaux snapshots existent pour le projet sélectionné.
- Q: Snapshots — quel est le point d'invocation unique de `save_snapshot` ? → A:
  `save_snapshot(project_data)` est appelée une seule fois par cycle de refresh réussi, à la fin de
  `_do_refresh`, jamais depuis un callback Dash. Un échec d'insertion est loggé silencieusement et
  ne plante pas le refresh principal.
- Q: `interval-15min` vs `interval-ui` — distinction stricte des outputs ? → A: `interval-ui` (1 s)
  est actif seulement pendant le loading (animation uniquement). `interval-15min` (900 000 ms,
  toujours actif) déclenche `force_refresh` dans `callbacks/sync.py`. Ces deux intervals ne partagent
  jamais les mêmes outputs.
- Q: Webhook Mailgun — vérification HMAC obligatoire ? → A: La route
  `/unifield/mailgun-webhook` DOIT vérifier HMAC-SHA256 (`MAILGUN_WEBHOOK_SIGNING_KEY`) avant tout
  traitement. Signature invalide → 403 sans log détaillé.
- Q: Authentification SSO en prod — périmètre du `before_request` et conditions du bypass ? → A:
  `before_request` sur `app.server` protège toutes les routes Dash (HTML → 302
  `/unifield/auth/login`, JSON → 401). Le bypass n'est activable que si
  `UNIFIELD_DEV_AUTH_BYPASS=true` ET `APP_ENV != production` sont tous deux vrais simultanément.
- Q: Seuils dans Gestion des Alertes — que change la migration de la sidebar vers l'onglet ? → A:
  Le store `store-seuils` conserve sa structure `{bt, ed, am, pd}` inchangée. Le callback
  `save_seuils` dans `callbacks/auth.py` reste branché sur les mêmes IDs `seuil-battery`,
  `seuil-ending`, `seuil-activity`. Seul le rendu HTML change d'emplacement (sidebar → onglet
  Alertes).
- Q: Dégradation gracieuse MongoDB — comportement précis en cas d'échec de refresh ? → A: Ne pas
  effacer le cache, mettre à jour uniquement le statut header (icône rouge + horodatage du dernier
  succès), logger l'erreur structurée, réessayer au cycle suivant (15 min) sans intervention
  manuelle.
- Q: Migration de contenu des onglets supprimés — destination de chaque onglet ? → A:
  `tab-urgences` → Onglet 1 Tableau de bord (`render_urgences` conservé) ;
  `tab-scores` → Onglet 3 Projets (fusionné dans `render_projets`) ;
  `tab-capteurs` → renommé Dispositifs (`render_capteurs` conservé, fichier renommé) ;
  `tab-qc` → supprimé (contenu non repris). `ui/tabs/scores.py` et `ui/tabs/qc.py` retirés du repo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Connexion SSO et accès sécurisé (Priority: P1)

Un opérateur CAD.42 ouvre le dashboard depuis le portail Z42. Il n'a pas de session active.
Le système le redirige vers Microsoft Entra ID via auth-api. Après authentification réussie,
le système vérifie que l'utilisateur possède un rôle autorisé (`admin` ou
`app:unifield:{admin,write,read}`) avant d'ouvrir une session. S'il n'a pas de rôle valide, il
reçoit un message d'erreur 403 explicite sans session créée.

**Why this priority**: Sans authentification fonctionnelle, aucun autre onglet ni donnée n'est
accessible. C'est le prérequis bloquant de toute la migration.

**Independent Test**: Naviguer vers `/unifield/` sans session → redirection Microsoft → retour avec
session valide → accès au tableau de bord. Tester aussi : utilisateur sans rôle → 403 visible sans
session.

**Acceptance Scenarios**:

1. **Given** un utilisateur sans session active, **When** il accède à `/unifield/`, **Then** il est
   redirigé vers la page de connexion Microsoft Entra ID via auth-api.
2. **Given** un utilisateur authentifié avec un rôle valide (`app:unifield:read`), **When** il
   complète le flow OAuth, **Then** une session est créée, son email est visible dans le header, et
   le tableau de bord s'affiche.
3. **Given** un utilisateur authentifié sans rôle `app:unifield:*` ni `admin`, **When** il complète
   le flow OAuth, **Then** aucune session n'est créée et il voit une page d'erreur 403 explicite.
4. **Given** un utilisateur avec une session active, **When** il clique sur "Déconnexion", **Then**
   la session est supprimée et il est redirigé vers la page de déconnexion auth-api.

---

### User Story 2 — Consultation du Tableau de bord opérationnel (Priority: P1)

Un opérateur connecté accède à l'onglet "Tableau de bord" (onglet par défaut). Il voit les urgences
actives (dispositifs hors schedule, batterie critique, inactivité prolongée, projets se terminant
bientôt) et un graphique d'évolution des états par projet sur les dernières heures. Le header affiche
les KPIs globaux et le statut de connexion MongoDB.

**Why this priority**: Vue synthétique principale — c'est la raison d'être opérationnelle du
dashboard. Elle regroupe les alertes critiques visibles en premier.

**Independent Test**: Avec des données en cache (issues d'un cycle MongoDB réussi), l'onglet Tableau
de bord affiche les urgences groupées et le graphique d'évolution. Le header affiche les bons KPIs.

**Acceptance Scenarios**:

1. **Given** des données en cache disponibles, **When** l'utilisateur arrive sur l'onglet "Tableau de
   bord", **Then** les urgences sont affichées groupées par criticité (critique / avertissement) avec
   projet, dispositif, type d'alerte et horodatage.
2. **Given** l'onglet Tableau de bord affiché, **When** l'utilisateur sélectionne un projet dans le
   dropdown et une plage (6h, 24h, 7 jours), **Then** le graphique d'évolution se met à jour avec
   les données de snapshots correspondantes sans déclencher un refresh global.
3. **Given** le header affiché, **When** les données sont chargées, **Then** les 5 KPIs globaux sont
   visibles : total projets actifs, dispositifs connectés, déconnectés, en alerte batterie, urgences
   actives.
4. **Given** une panne MongoDB, **When** le cycle de refresh échoue, **Then** le header affiche un
   indicateur rouge + horodatage du dernier succès, et les données du cache précédent restent
   affichées.

---

### User Story 3 — Supervision des dispositifs (Priority: P2)

Un opérateur accède à l'onglet "Dispositifs". Il filtre par état de connexion, niveau de batterie
et projet. Il consulte la table paginée (50 lignes). Il clique sur une ligne pour voir le détail
complet du dispositif dans un panneau ou modal.

**Why this priority**: Vue opérationnelle quotidienne pour surveiller l'état de chaque tracker.
Dépend du cache (US2) mais pas du graphique d'évolution.

**Independent Test**: Avec des données en cache, filtrer "Déconnectés" + "Batterie critique" → la
table affiche uniquement les dispositifs correspondants. Clic sur une ligne → modal avec détails.

**Acceptance Scenarios**:

1. **Given** des données en cache disponibles, **When** l'utilisateur accède à l'onglet "Dispositifs",
   **Then** une table paginée de 50 lignes s'affiche avec toutes les colonnes triables.
2. **Given** la table affichée, **When** l'utilisateur applique les filtres connexion, batterie et
   projet, **Then** la table se met à jour pour n'afficher que les dispositifs correspondants.
3. **Given** la table filtrée, **When** l'utilisateur clique sur une ligne, **Then** un panneau ou
   modal s'ouvre avec le détail complet du dispositif (toutes les métadonnées disponibles).

---

### User Story 4 — Consultation des projets et scores (Priority: P2)

Un opérateur accède à l'onglet "Projets". Il voit les cartes de projet avec nom, code, dates,
dispositifs actifs/total, score santé et statut. Il filtre par type, statut ou recherche textuelle.
Il développe un projet pour voir le détail : description, dispositifs attachés, graphe couverture
temporelle, score qualité détaillé.

**Why this priority**: Fournit la vue managériale par projet. Fusionne les anciens onglets Projets
et Scores pour réduire la navigation.

**Independent Test**: Avec des données en cache, l'onglet Projets affiche les cartes. Filtrage
"Actif" → seuls les projets actifs. Clic sur un projet → détail avec score qualité visible.

**Acceptance Scenarios**:

1. **Given** des données en cache disponibles, **When** l'utilisateur accède à l'onglet "Projets",
   **Then** les cartes de projet affichent : nom, code, dates, dispositifs actifs/total, score santé,
   statut (Actif / Se termine bientôt / Archivé).
2. **Given** les cartes affichées, **When** l'utilisateur applique un filtre ou une recherche
   textuelle, **Then** seules les cartes correspondantes sont visibles.
3. **Given** une carte de projet visible, **When** l'utilisateur clique pour le détail, **Then**
   il voit : description, dispositifs attachés, graphe couverture temporelle, score qualité détaillé.

---

### User Story 5 — Supervision et configuration des alertes (Priority: P3)

Un opérateur accède à l'onglet "Gestion des Alertes". Il consulte l'historique des 50 dernières
alertes envoyées par `alerter.py` (date, sujet, nb problèmes, destinataires, statut Mailgun). Il
voit le statut du service alerter (dernier cycle, nb problèmes actifs, prochaine exécution). Il peut
modifier les seuils de déclenchement (batterie, fin imminente, inactivité).

**Why this priority**: Fonctionnalité de supervision SMSI importante mais non bloquante pour la
valeur opérationnelle principale. `alerter.py` fonctionne indépendamment du dashboard.

**Independent Test**: Avec des données dans `alert_history`, l'onglet affiche la table d'historique.
Modifier un seuil → la valeur est sauvegardée dans `store-seuils` et visible après rechargement.

**Acceptance Scenarios**:

1. **Given** des entrées dans la collection `alert_history`, **When** l'utilisateur accède à l'onglet
   "Gestion des Alertes", **Then** les 50 dernières alertes sont affichées avec date, sujet, nb
   problèmes, destinataires, statut Mailgun.
2. **Given** l'onglet affiché, **When** les données du service alerter sont disponibles, **Then**
   le statut du service (dernier cycle, problèmes actifs, prochaine exécution) est visible.
3. **Given** le formulaire de seuils affiché, **When** l'utilisateur modifie un seuil et valide,
   **Then** la nouvelle valeur est persistée dans `store-seuils` (structure `{bt, ed, am, pd}`) et
   prise en compte par le cycle d'alerte suivant.

---

### Edge Cases

- Que se passe-t-il si MongoDB est indisponible au démarrage de l'application ? → L'application
  démarre, affiche un indicateur d'erreur rouge dans le header avec horodatage "jamais chargé",
  et attend le premier cycle de refresh automatique (15 min) ou un clic sur "Actualiser".
- Que se passe-t-il si le cookie de session expire pendant une navigation active ? → L'utilisateur
  est redirigé vers `/unifield/auth/login` au prochain appel de route serveur (HTML → 302,
  JSON → 401).
- Que se passe-t-il si la collection `snapshots` est vide (premier démarrage) ? → Le graphique
  d'évolution de l'Onglet 1 affiche un état vide avec un message explicatif.
- Que se passe-t-il si l'utilisateur clique "Actualiser" pendant un refresh déjà en cours ? → Le
  bouton est désactivé pendant le refresh ; un second clic est ignoré.
- Que se passe-t-il si `alerter.py` n'a encore jamais écrit dans `alert_history` ? → L'onglet 4
  affiche un historique vide avec un message explicatif.
- Que se passe-t-il en développement local avec bypass activé ? → Le formulaire email/clé
  historique est présenté uniquement si `UNIFIELD_DEV_AUTH_BYPASS=true` ET `APP_ENV != production`
  sont tous deux définis.
- Que se passe-t-il si `save_snapshot` échoue lors d'un cycle de refresh ? → L'erreur est loggée
  silencieusement ; le refresh principal est considéré réussi ; les données sont mises en cache
  normalement.
- Que se passe-t-il si la route `/unifield/mailgun-webhook` reçoit un appel avec signature HMAC
  invalide ? → Retour 403 immédiat sans log détaillé (prévention de la fuite d'information).

## Requirements *(mandatory)*

### Functional Requirements

**Migration source de données (REST → MongoDB)**

- **FR-001**: Le système DOIT remplacer `api/loader.py` + `api/client.py` par `api/mongo_loader.py`
  produisant une interface de sortie identique (clés : `projects`, `project_data`, `all_units`,
  `all_trackers`, `all_events`, `qc`, `loaded_at`) afin de ne modifier aucun callback existant.
  La conformité DOIT être validée par diff structurel contre un jeu de référence figé depuis le
  loader REST. Tout écart de champ ou d'enrichissement `_*` (`_is_connected`, `_battery_volt`, etc.)
  est un bug de mapping à corriger dans `api/mongo_loader.py`.
- **FR-002**: Le chargement DOIT s'effectuer en 2 temps : (1) vue légère `projects` + `trackers`
  pour tous les projets ; (2) détail `units`, `events`, `schedule`, `scores` pour les projets actifs
  uniquement (`archived == False` ET `endDate > utcnow()`). Si MongoDB stocke des champs à plat
  (par exemple `battery` hors de `lastTrack.message`), c'est `api/mongo_loader.py` qui réécrit les
  données vers la forme attendue par `business/`. `business/trackers.py` n'est jamais modifié.
- **FR-003**: L'association tracker → projet DOIT être réalisée en Python sans `$lookup`.
- **FR-004**: Un `MongoClient` singleton DOIT être partagé sur toute la durée de vie du process,
  créé de façon lazy au premier accès par worker (jamais instancié au niveau module). Paramètres de
  pool obligatoires : `maxPoolSize=20`, `minPoolSize=3`, `connectTimeoutMS=10000`,
  `socketTimeoutMS=15000`, `maxIdleTimeMS=60000`. Les signatures `get_cached_data(email, key)` de
  `cache.py` sont conservées mais ignorent les arguments en interne : la clé `md5(email:key)` est
  supprimée au profit d'une clé fixe unique par process.
- **FR-005**: En cas d'échec de refresh MongoDB (timeout, connexion refusée ou autre exception),
  le cache existant DOIT être conservé sans modification ; le header DOIT afficher un indicateur
  d'erreur rouge avec l'horodatage du dernier refresh réussi ; l'erreur DOIT être loggée de façon
  structurée ; le prochain cycle automatique (15 min) DOIT réessayer sans intervention manuelle.
  L'application ne DOIT PAS crasher.
- **FR-006**: À chaque cycle de refresh réussi, `cache.py` DOIT appeler une seule fois
  `save_snapshot(project_data)` à la fin de `_do_refresh`, jamais depuis un callback Dash. Cette
  fonction insère un document `{ project_id, ts, connected, disconnected, battery_low }` dans la
  collection `snapshots`. Un échec d'insertion DOIT être loggé silencieusement et ne DOIT PAS
  interrompre le cycle de refresh.

**Migration authentification (formulaire → SSO Microsoft)**

- **FR-007**: Le système DOIT implémenter le flow Microsoft Authorization Code via auth-api avec les
  routes `/auth/login`, `/auth/complete`, `/auth/logout`, `/auth/me` sur `app.server`. Un
  middleware `before_request` sur `app.server` DOIT protéger toutes les routes Dash : les requêtes
  HTML sans session valide reçoivent un `302` vers `/unifield/auth/login` ; les requêtes JSON sans
  session valide reçoivent un `401`.
- **FR-008**: Le cookie de session DOIT être nommé `unifield.sid` avec attributs `httpOnly`,
  `SameSite=Lax`, `Secure` (HTTPS uniquement).
- **FR-009**: Le rôle de l'utilisateur DOIT être vérifié via auth-api **avant** toute création de
  session. Un utilisateur sans rôle `admin` ni `app:unifield:{admin,write,read}` DOIT recevoir un
  403 explicite sans session créée.
- **FR-010**: Le formulaire email/clé historique DOIT être accessible uniquement lorsque les deux
  conditions suivantes sont simultanément vraies : `UNIFIELD_DEV_AUTH_BYPASS=true` ET
  `APP_ENV != production`. Il est absent et non-activable en tout autre contexte.
- **FR-011**: La session DOIT stocker le hash SHA-256 de l'identifiant de session en RAM. Aucun
  secret ou identifiant brut ne DOIT être stocké en clair.

**Refonte layout (sidebar + 5 onglets → header SMSI + 4 onglets)**

- **FR-012**: La sidebar (`ui/sidebar.py`) DOIT être supprimée du layout en production.
- **FR-013**: Un header horizontal fixe DOIT être présent sur toutes les vues, contenant : titre,
  email utilisateur connecté, date/heure du dernier refresh, statut MongoDB (vert/rouge), bouton
  "Actualiser", 5 KPIs globaux, et 4 onglets de navigation.
- **FR-014**: Les 4 onglets DOIVENT être : [Tableau de bord] [Dispositifs] [Projets]
  [Gestion des Alertes]. L'onglet par défaut au chargement est [Tableau de bord] (valeur
  `"dashboard"`). Le store `active-tab` est la seule source de vérité de l'onglet actif ;
  la classe CSS active est calculée depuis ce store, jamais depuis `n_clicks` direct. Un seul
  callback gère la mise à jour de `active-tab` (reçoit les 4 `n_clicks`, émet la nouvelle valeur).
- **FR-015**: Les anciens onglets DOIVENT être migrés ou supprimés comme suit :
  `tab-urgences` → contenu absorbé dans l'Onglet 1 (`render_urgences()` conservé) ;
  `tab-scores` → contenu absorbé dans l'Onglet 3 (`render_scores()` fusionné dans `render_projets()`) ;
  `tab-capteurs` → renommé Dispositifs (`render_capteurs()` conservé, fichier renommé
  `ui/tabs/dispositifs.py`) ;
  `tab-qc` → supprimé, contenu non repris dans les nouveaux onglets.
  Les fichiers `ui/tabs/scores.py` et `ui/tabs/qc.py` DOIVENT être retirés du dépôt.

**Onglet 1 — Tableau de bord**

- **FR-016**: L'onglet DOIT afficher les urgences en reprenant `render_urgences()` de
  `ui/tabs/urgences.py`, groupées par criticité (critique / avertissement).
- **FR-017**: L'onglet DOIT afficher un graphique `go.Scatter` (évolution des états) avec axe X =
  timestamps snapshots, axe Y = nb connectés / déconnectés / batterie faible. Un dropdown de projet
  et un sélecteur de plage (6h, 24h, 7 jours) DOIVENT contrôler ce graphique via un callback Dash
  dédié, séparé du callback de rendu principal. Ce callback DOIT écouter uniquement le projet
  sélectionné et la plage temporelle ; il ne DOIT PAS se déclencher à chaque refresh 15 min sauf
  si de nouveaux snapshots existent pour le projet sélectionné.

**Onglet 2 — Dispositifs**

- **FR-018**: L'onglet DOIT reprendre `render_capteurs()` de `ui/tabs/capteurs.py` (renommé
  `ui/tabs/dispositifs.py`) avec des filtres connexion, batterie, projet (multi-select) et une table
  paginée à 50 lignes triable sur toutes les colonnes.
- **FR-019**: Un clic sur une ligne DOIT ouvrir un panneau ou modal avec le détail complet du
  dispositif.

**Onglet 3 — Projets**

- **FR-020**: L'onglet DOIT fusionner `render_projets()` et `render_scores()` dans `ui/tabs/projets.py`
  mis à jour, affichant des cartes de projet avec nom, code, dates, dispositifs actifs/total, score
  santé, statut.
- **FR-021**: Des filtres type, statut et recherche textuelle DOIVENT être disponibles. Le détail
  projet DOIT inclure graphe couverture temporelle et score qualité détaillé.

**Onglet 4 — Gestion des Alertes**

- **FR-022**: L'onglet DOIT afficher les 50 dernières entrées de `alert_history` (date, sujet, nb
  problèmes, destinataires, statut Mailgun) en lecture seule.
- **FR-023**: L'onglet DOIT afficher le statut du service alerter (dernier cycle, problèmes actifs,
  prochaine exécution).
- **FR-024**: Les 3 inputs de seuils (`seuil-battery`, `seuil-ending`, `seuil-activity`) DOIVENT
  migrer de `ui/sidebar.py` vers `ui/tabs/alertes.py`. Le store `store-seuils` conserve sa structure
  `{bt, ed, am, pd}` inchangée. Le callback `save_seuils` dans `callbacks/auth.py` reste branché
  sur les mêmes IDs — seule la position HTML change (sidebar → onglet Alertes).

**Refresh et infrastructure**

- **FR-025**: Un `interval-15min` (900 000 ms, toujours actif) DOIT déclencher `force_refresh` dans
  `callbacks/sync.py`. Un `interval-ui` (1 s) DOIT être distinct, actif seulement pendant le
  chargement (animation uniquement). Ces deux intervals ne DOIVENT jamais partager les mêmes
  outputs Dash.
- **FR-026**: Le dashboard DOIT être servi sous le préfixe `/unifield/` avec
  `requests_pathname_prefix='/unifield/'`. La configuration nginx DOIT être sans strip du préfixe.
- **FR-027**: `alerter.py` DOIT écrire `{ ts, subject, issues_count, recipients, mailgun_status }`
  dans `alert_history` à chaque envoi d'alerte.
- **FR-028**: La route `/unifield/mailgun-webhook` DOIT vérifier le HMAC-SHA256 de la requête
  entrante en utilisant `MAILGUN_WEBHOOK_SIGNING_KEY` avant tout traitement. Une signature invalide
  DOIT retourner un `403` immédiatement, sans log détaillé.

### Key Entities

- **Snapshot** : `{ project_id, ts, connected, disconnected, battery_low }` — enregistrement
  périodique de l'état agrégé d'un projet, écrit par le dashboard (`cache.py` via `save_snapshot`),
  lu par l'Onglet 1.
- **AlertHistory** : `{ ts, subject, issues_count, recipients, mailgun_status }` — enregistrement
  d'un envoi d'alerte, écrit exclusivement par `alerter.py`, lu par l'Onglet 4 en lecture seule.
- **Session utilisateur** : identifiant de session (hash SHA-256), email SSO, rôle vérifié —
  stockée en RAM, accessible via cookie `unifield.sid`.
- **CacheServeur** : dictionnaire Python contenant `{ projects, project_data, all_units,
  all_trackers, all_events, qc, loaded_at }` — seule source de données pour tous les callbacks Dash.
  Clé interne unique par process (clé `md5(email:key)` supprimée).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un utilisateur authentifié accède au tableau de bord en moins de 3 secondes après
  le retour du flow SSO (hors latence réseau Microsoft).
- **SC-002**: Le rechargement complet des données (cycle MongoDB 2-temps) ne bloque pas l'interface
  utilisateur — les données précédentes restent affichées pendant le rechargement.
- **SC-003**: 100 % des callbacks Dash existants fonctionnent sans modification de leur logique après
  la migration REST → MongoDB (iso-interface validée par diff structurel contre le jeu de référence
  REST).
- **SC-004**: Un utilisateur sans rôle valide reçoit un 403 explicite en moins de 2 secondes, sans
  session créée.
- **SC-005**: Le cycle de refresh automatique se déclenche toutes les 15 minutes ± 5 secondes sans
  intervention utilisateur.
- **SC-006**: En cas de panne MongoDB, l'application continue d'afficher les données du dernier cache
  valide et indique visuellement l'erreur dans le header (indicateur rouge + horodatage dernier
  succès).
- **SC-007**: L'onglet Dispositifs affiche jusqu'à 50 lignes paginées sans dégradation perceptible
  de l'interface, quel que soit le nombre total de dispositifs en cache.
- **SC-008**: Zéro secret (URI MongoDB, secret auth-api, clés Mailgun) ne doit apparaître dans les
  logs applicatifs ni dans le code source commité.
- **SC-009**: La sélection d'un projet ou d'une plage temporelle dans le graphique d'évolution ne
  déclenche pas de rechargement global des données métier — uniquement le callback dédié snapshots.

## Assumptions

- L'infrastructure auth-api (ServiceConsumer) est opérationnelle et accessible depuis la VM Ubuntu.
  Le slug `unifield` y est déjà enregistré ou sera enregistré avant le déploiement.
- Les collections MongoDB Atlas (`projects`, `trackers`, `units`, `events`, `schedule`, `scores`,
  `snapshots`, `alert_history`) sont créées et accessibles avec les droits appropriés :
  lecture seule pour les collections métier, lecture+écriture pour `snapshots` (dashboard) et
  `alert_history` (alerter.py uniquement).
- Les variables d'environnement (`UNIFIELD_MONGO_URI`, `AUTH_API_SERVICE_CONSUMER_SECRET`,
  `MAILGUN_API_KEY`, `MAILGUN_WEBHOOK_SIGNING_KEY`, `APP_ENV`) sont provisionnées sur la VM avant
  déploiement.
- Un seul worker Gunicorn est utilisé (`--workers 1 --threads 4`), ce qui rend le singleton
  `MongoClient` et le cache en RAM techniquement sûrs sans verrou inter-process.
- Le reverse proxy nginx est déjà configuré pour passer le préfixe `/unifield/` sans le supprimer
  (pass-through).
- `alerter.py` est le seul processus habilité à écrire dans `alert_history`. Le dashboard écrit
  uniquement dans `snapshots` (via `save_snapshot`) et est en lecture seule sur toutes les autres
  collections y compris `alert_history`.
- La logique métier contenue dans `business/trackers.py`, `flags.py`, `schedule.py`, `segments.py`,
  `alerts.py` est correcte et validée — aucune régression de comportement n'est attendue.
- Le support mobile n'est pas dans le périmètre de cette migration (interface desktop uniquement).
- Les tests automatisés ne sont pas dans le périmètre de cette spécification (l'iso-interface est
  validée par diff structurel en recette).

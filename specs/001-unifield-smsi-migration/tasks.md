---
description: "Tasks: Migration UNIFIELD — Console SMSI CAD.42"
---

# Tasks: Migration UNIFIELD — Console SMSI CAD.42

**Input**: Design documents from `specs/001-unifield-smsi-migration/`
**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅ | quickstart.md ✅

**Tests**: Tests pytest inclus pour `auth/role_check.py` et `auth/session_store.py` (explicitement
requis dans spec.md). Recette manuelle staging en phase finale.

**Organization**: Phases par user story pour permettre une implémentation et une validation
indépendantes. Les phases 1 et 2 (Setup + Foundational) DOIVENT être complètes avant toute
user story.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Parallélisable (fichiers différents, aucune dépendance sur une tâche incomplète)
- **[Story]**: User story cible (US1 à US5)
- Chemins de fichiers absolus dans les descriptions

---

## Phase 1 : Setup

**Objectif**: Initialisation de l'environnement et des variables de configuration.

- [X] T001 Mettre à jour `config.py` : ajouter `UNIFIELD_MONGO_URI`, `UNIFIELD_MONGO_DB`,
  `BASE_PATH=/unifield/`, `PUBLIC_URL`, `APP_ENV`, `UNIFIELD_SOURCE` (valeur par défaut `"mongo"`).
  Lire depuis `os.environ` avec fallback `python-dotenv`. Ne jamais logger ces valeurs.
- [X] T002 [P] Créer `.env.example` à la racine du projet avec toutes les variables d'environnement
  requises et des valeurs fictives. Ne pas créer `.env` (listé dans `.gitignore`). Référencer
  `quickstart.md` pour le format complet.
- [X] T003 [P] Mettre à jour `requirements.txt` : vérifier la présence de `pymongo>=4.0`,
  `dash==2.17.*`, `plotly==5.21.*`, `gunicorn==22.*`, `python-dotenv`, `requests`. Aucune
  dépendance supplémentaire non listée dans la constitution.

---

## Phase 2 : Foundational — MongoDB, Cache et Layout de base

**Objectif**: Infrastructure MongoDB (loader iso-interface + cache singleton) et structure visuelle
de base (header SMSI + 4 onglets) qui DOIVENT être complètes avant toute user story.

**⚠️ CRITIQUE**: Aucune user story ne peut être implémentée avant la fin de cette phase.

- [X] T004 Créer `api/mongo_client.py` : exposer `get_client()` qui retourne un `MongoClient`
  singleton créé de façon lazy au premier appel (jamais au niveau module, post-fork safe).
  Paramètres obligatoires : `maxPoolSize=20`, `minPoolSize=3`, `connectTimeoutMS=10000`,
  `socketTimeoutMS=15000`, `maxIdleTimeMS=60000`. URI depuis `config.UNIFIELD_MONGO_URI`.
  Ne jamais logger l'URI.
- [ ] T005 [P] Générer le jeu de référence REST figé pour validation iso-interface :
  exécuter `UNIFIELD_SOURCE=rest python -c "import json, cache; ..."` (voir `quickstart.md`)
  et sauvegarder le résultat dans `specs/001-unifield-smsi-migration/ref_rest.json`.
  Ce fichier ne doit pas être commité (ajouter à `.gitignore`).
- [X] T006 Créer `api/mongo_loader.py` : implémenter `load_all_data()` qui retourne un dictionnaire
  avec exactement les mêmes clés que `api/loader.py` : `projects`, `project_data`, `all_units`,
  `all_trackers`, `all_events`, `qc`, `loaded_at`. Chargement 2-temps :
  (1) `projects` + `trackers` pour tous les projets via `get_client()` ;
  (2) `units`, `events`, `schedule`, `scores` uniquement pour les projets actifs
  (`archived == False AND endDate > utcnow()`). Association tracker→projet en Python (jamais
  `$lookup`). Couche d'adaptation des champs : si `battery` est stocké à plat dans MongoDB
  (pas dans `lastTrack.message`), le réécrire vers `lastTrack.message.battery_volt`. Calculer
  les enrichissements `_is_connected`, `_battery_volt`, `_project_name` identiques à `api/loader.py`.
- [ ] T007 Valider l'iso-interface : exécuter le diff `ref_rest.json` vs sortie de `mongo_loader.py`
  (voir `quickstart.md`). Corriger tout écart de clé ou d'enrichissement `_*` dans
  `api/mongo_loader.py` jusqu'à diff = 0. Documenter le résultat dans
  `specs/001-unifield-smsi-migration/progress-log.md` (ACTION-014).
- [X] T008 Refactoriser `cache.py` :
  (a) Remplacer l'import `api.loader` par `api.mongo_loader` si `UNIFIELD_SOURCE == "mongo"`,
  conserver `api.loader` comme fallback si `UNIFIELD_SOURCE == "rest"` ;
  (b) Supprimer la clé `md5(email:key)` — conserver les signatures `get_cached_data(email, key)`
  et `set_cached_data(email, key, data)` mais utiliser une clé fixe interne unique par process ;
  (c) Ajouter `save_snapshot(project_data)` appelée une seule fois à la fin de `_do_refresh`
  (jamais depuis un callback) — insère `{ project_id, ts, connected, disconnected, battery_low }`
  dans la collection `snapshots` via `get_client()`. Échec d'insertion : logguer silencieusement
  et continuer. Mettre à jour `_mongo_ok` et `_last_success` dans le dict de cache.
- [X] T009 [P] Modifier `alerter.py` : à chaque envoi d'alerte Mailgun réussi, insérer un document
  `{ ts, subject, issues_count, recipients, mailgun_status }` dans la collection `alert_history`
  via `get_client()` (mêmes paramètres pool que `api/mongo_client.py`). Ne pas modifier la logique
  d'alerte existante. Logguer l'insertion de façon structurée : `{"event": "alert_sent", ...}`.
- [X] T010 Modifier `ui/layout.py` :
  (a) Supprimer l'import de `ui/sidebar.py` et tout composant sidebar du layout ;
  (b) Créer le header horizontal fixe contenant dans l'ordre : titre "Tableau de bord opérationnel
  UNIFIELD — CAD.42", email utilisateur (depuis `dcc.Store(id="store-creds")`), date/heure dernier
  refresh, indicateur statut MongoDB (id `conn-status-indicator` : vert/rouge depuis
  `dcc.Store(id="conn-status")`), bouton "Actualiser" (id `btn-refresh`), rangée de 5 KPIs
  (id `kpi-bar`), 4 boutons onglet (ids `btn-tab-dashboard`, `btn-tab-dispositifs`,
  `btn-tab-projets`, `btn-tab-alertes`) ;
  (c) Ajouter `dcc.Store(id="active-tab", data="dashboard")` et `dcc.Store(id="conn-status")` ;
  (d) Ajouter `dcc.Interval(id="interval-15min", interval=900000, disabled=False)` et
  `dcc.Interval(id="interval-ui", interval=1000, disabled=True)` ;
  (e) Ajouter une `dcc.Location(id="url")` pour la navigation si absente ;
  (f) Créer la zone de contenu principale (id `tab-content`) sans sidebar.
- [X] T011 [P] Modifier `callbacks/sync.py` :
  (a) Brancher `interval-15min` sur `force_refresh` : callback qui appelle `cache.py` et met à jour
  `dcc.Store(id="conn-status")` avec `{ok: True/False, last_success: "...ISO..."}` ;
  (b) Ajouter la gestion de dégradation gracieuse : si MongoDB échoue, conserver le cache existant,
  mettre à jour `conn-status` avec `ok=False` et `last_success` de la dernière réussite, logger
  l'erreur structurée `{"event": "mongo_refresh_failed", "error": "...", "ts": "..."}` ;
  (c) `interval-ui` (1 s) ne partage AUCUN output avec `interval-15min`.
- [X] T012 [P] Supprimer les fichiers retirés du plan :
  `ui/sidebar.py`, `ui/tabs/scores.py`, `ui/tabs/qc.py`.
  Vérifier qu'aucun import de ces fichiers ne subsiste dans le reste du code avant suppression.
  Documenter dans `progress-log.md` (ACTION-021).

**Checkpoint Foundational**: MongoDB charge les données, cache singleton fonctionne, header SMSI
s'affiche avec les 4 onglets, interval-15min déclenche un refresh et met à jour `conn-status`.

---

## Phase 3 : User Story 1 — Connexion SSO et accès sécurisé (Priority: P1) 🎯 MVP

**Goal**: Remplacer le formulaire email/clé par le flow SSO Microsoft Entra ID via auth-api.
Toutes les routes sont protégées par `before_request`. Un utilisateur sans rôle reçoit un 403
explicite sans session créée.

**Independent Test**: Naviguer vers `/unifield/` sans session → 302 `/unifield/auth/login` →
flow Microsoft → retour avec email dans header. Utilisateur sans rôle `app:unifield:*` → 403
visible. Pytest `test_role_check.py` + `test_session_store.py` passent.

### Implémentation User Story 1

- [X] T013 [P] [US1] Créer `auth/__init__.py` (vide) et `auth/role_check.py` : implémenter
  `check_role(user_info: dict) -> str` qui inspecte les rôles retournés par auth-api et retourne
  le premier rôle valide parmi `admin`, `app:unifield:admin`, `app:unifield:write`,
  `app:unifield:read`. Lever `NoUnifieldRoleError` (exception personnalisée définie dans ce module)
  si aucun rôle valide n'est trouvé. Pas d'autre logique dans ce module.
- [X] T014 [P] [US1] Créer `auth/session_store.py` : dict RAM `_sessions = {}` avec clé
  `sha256(sid)`. Implémenter `create_session(email, role) -> sid`, `get_session(sid) -> dict|None`,
  `delete_session(sid) -> None`, `cleanup_expired() -> None` (supprimer les sessions expirées TTL
  24h). Aucune persistance sur disque. `sha256` calculé via `hashlib`.
- [X] T015 [P] [US1] Créer `auth/session_cookie.py` : implémenter `set_cookie(response, sid)` qui
  pose le cookie `unifield.sid` avec `httponly=True`, `samesite="Lax"`, `secure=True` (si HTTPS),
  `path="/unifield/"`, `max_age=86400`. Implémenter `get_cookie(request) -> str|None` qui lit
  la valeur du cookie `unifield.sid` depuis la requête.
- [X] T016 [US1] Créer `auth/microsoft_flow.py` : implémenter `build_auth_url(state) -> str`
  (construit l'URL de redirection Microsoft via auth-api avec `state` et `redirect_uri`),
  et `exchange_code(code, state) -> dict` (échange le code contre les infos utilisateur via
  une requête POST à auth-api ServiceConsumer slug `"unifield"`). Le secret auth-api est lu depuis
  `config.AUTH_API_SERVICE_CONSUMER_SECRET`, jamais loggé.
- [X] T017 [US1] Créer `auth/routes.py` : Blueprint Flask avec 4 routes enregistrées sous
  `/unifield/auth/` :
  - `GET /login` → `build_auth_url(state)` + stocker `state` en session temporaire + 302
  - `GET /complete` → valider `state`, appeler `exchange_code`, appeler `check_role`,
    si OK : `create_session` + `set_cookie` + 302 `/unifield/`,
    si `NoUnifieldRoleError` : retourner 403 page explicite "Accès refusé — aucun rôle UNIFIELD"
    sans créer de session
  - `GET /logout` → `delete_session(get_cookie(request))` + expirer cookie + 302 page déconnexion
  - `GET /me` → retourner JSON `{email, role}` si session valide, sinon 401
- [X] T018 [US1] Modifier `app.py` :
  (a) Ajouter `requests_pathname_prefix="/unifield/"` et `routes_pathname_prefix="/unifield/"` à
  l'init Dash ;
  (b) Enregistrer le Blueprint `auth.routes` sur `app.server` ;
  (c) Enregistrer la route `POST /unifield/mailgun-webhook` (voir T037) ;
  (d) Implémenter `@app.server.before_request` :
  - Laisser passer les routes `/unifield/auth/*` et `/unifield/mailgun-webhook`
  - Si `APP_ENV == "production"` OU `UNIFIELD_DEV_AUTH_BYPASS != "true"` :
    - Vérifier `session_store.get_session(get_cookie(request))`
    - Sans session valide : JSON → 401, HTML → 302 `/unifield/auth/login`
  - Si bypass activé (double condition : `UNIFIELD_DEV_AUTH_BYPASS=true` ET `APP_ENV != production`) :
    laisser passer sans vérification
- [X] T019 [US1] Modifier `callbacks/auth.py` : le callback qui peuple `store-creds` doit lire
  l'email et le rôle depuis la session SSO (via `session_store.get_session(cookie)`) au lieu du
  formulaire email/clé. Conserver le formulaire email/clé UNIQUEMENT sous condition
  `UNIFIELD_DEV_AUTH_BYPASS=true AND APP_ENV != production`. Les IDs de composant Dash ne changent
  pas (compatibilité callback existant).

### Tests User Story 1

- [X] T020 [P] [US1] Créer `tests/test_role_check.py` :
  - Test rôle `admin` → retourne `"admin"`
  - Test rôle `app:unifield:read` → retourne `"app:unifield:read"`
  - Test rôle `app:unifield:write` → retourne `"app:unifield:write"`
  - Test aucun rôle valide → lève `NoUnifieldRoleError`
  - Test rôle non-unifield seul → lève `NoUnifieldRoleError`
- [X] T021 [P] [US1] Créer `tests/test_session_store.py` :
  - Test `create_session` → retourne un sid (string non vide)
  - Test `get_session(sid)` → retourne dict avec `email`, `role`
  - Test `get_session(sid_inconnu)` → retourne `None`
  - Test `delete_session(sid)` → `get_session` retourne `None` ensuite
  - Test `cleanup_expired` → supprime les sessions dont `expires_at` est passé
  - Exécuter : `pytest tests/test_role_check.py tests/test_session_store.py -v`

**Checkpoint US1**: Login Microsoft → email visible dans header, 403 explicite sans rôle,
`pytest` vert sur les 2 fichiers de test.

---

## Phase 4 : User Story 2 — Tableau de bord opérationnel (Priority: P1)

**Goal**: Onglet par défaut affichant les urgences groupées (depuis `render_urgences()`) et le
graphique d'évolution des états par projet (depuis la collection `snapshots`).

**Independent Test**: Avec données en cache, l'onglet Tableau de bord affiche urgences groupées.
Après 2 cycles de refresh (30 min), le graphique d'évolution affiche des points.

### Implémentation User Story 2

- [X] T022 [US2] Créer `ui/tabs/dashboard.py` : implémenter `render_dashboard(data)` qui :
  (a) appelle `render_urgences(data)` importé depuis `ui/tabs/urgences.py` pour afficher les
  urgences groupées par criticité (critique / avertissement) avec projet, dispositif, type
  d'alerte, horodatage ;
  (b) inclut la structure HTML pour le graphique d'évolution : `dcc.Dropdown(id="snap-project")`,
  `dcc.RadioItems(id="snap-range", options=["6h","24h","7j"])`,
  `dcc.Graph(id="snap-graph")`.
  La fonction ne charge pas de données MongoDB directement.
- [X] T023 [US2] Modifier `callbacks/tabs.py` :
  (a) Ajouter le callback `update_active_tab` : `Input("btn-tab-dashboard", "n_clicks")`,
  `Input("btn-tab-dispositifs", "n_clicks")`, `Input("btn-tab-projets", "n_clicks")`,
  `Input("btn-tab-alertes", "n_clicks")` → `Output("active-tab", "data")`. Utiliser
  `callback_context` pour identifier quel bouton a déclenché. Valeur par défaut `"dashboard"` ;
  (b) Ajouter le callback `render_tab_content` : `Input("active-tab", "data")` + cache data →
  `Output("tab-content", "children")`. Appelle `render_dashboard`, `render_dispositifs`,
  `render_projets`, `render_alertes` selon la valeur de `active-tab` ;
  (c) Ajouter le callback CSS `update_tab_buttons` : `Input("active-tab", "data")` →
  `Output("btn-tab-dashboard", "className")`, ...(x4). La classe `"active"` est appliquée
  au bouton correspondant à la valeur du store, jamais calculée depuis `n_clicks`.
- [X] T024 [US2] Ajouter le callback dédié snapshots dans `callbacks/tabs.py` :
  `Input("snap-project", "value")` + `Input("snap-range", "value")` →
  `Output("snap-graph", "figure")`. Ce callback lit directement depuis MongoDB collection
  `snapshots` (via `get_client()`) selon le projet et la plage sélectionnés (6h = 6 dernières
  heures UTC, 24h, 7j). Construire un `go.Scatter` avec axe X = timestamps, axe Y = 3 séries
  (connected, disconnected, battery_low). Si collection vide → retourner figure vide avec
  annotation "Aucune donnée disponible — les données apparaîtront après le premier cycle de
  refresh". Ce callback ne partage AUCUN output avec `interval-15min`.
- [X] T025 [P] [US2] Mettre à jour le callback KPIs dans `callbacks/sync.py` : calculer et
  émettre vers `Output("kpi-bar", "children")` : total projets actifs, dispositifs connectés,
  dispositifs déconnectés, dispositifs en alerte batterie, urgences actives. Données depuis
  le cache (`get_cached_data()`).

**Checkpoint US2**: Onglet Tableau de bord visible par défaut, urgences affichées, graphe
snapshots s'alimente après 2 cycles (30 min), navigation entre onglets fonctionne.

---

## Phase 5 : User Story 3 — Supervision des dispositifs (Priority: P2)

**Goal**: Onglet "Dispositifs" avec filtres (connexion, batterie, projet multi-select), table
paginée 50 lignes triable, modal de détail sur clic de ligne.

**Independent Test**: Filtrer "Déconnectés" + "Batterie critique" → table correctement filtrée.
Clic sur une ligne → modal avec toutes les métadonnées.

### Implémentation User Story 3

- [X] T026 [P] [US3] Renommer `ui/tabs/capteurs.py` → `ui/tabs/dispositifs.py` sans modifier
  `render_capteurs()`. Mettre à jour tous les imports vers l'ancien fichier dans le code.
- [X] T027 [US3] Étendre `ui/tabs/dispositifs.py` : wrapper `render_dispositifs(data)` qui appelle
  `render_capteurs(data)` et ajoute les filtres :
  - `dcc.Dropdown(id="filter-connexion", options=["Tous","Connectés","Déconnectés"], value="Tous")`
  - `dcc.Dropdown(id="filter-batterie", options=["Tous","Critique","Faible","OK"], value="Tous")`
  - `dcc.Dropdown(id="filter-projet", multi=True, id="filter-projet-multi")`
  La table (composant `dash_table.DataTable`) doit avoir `page_size=50`, `sort_action="native"`,
  `row_selectable="single"`, id `table-dispositifs`.
- [X] T028 [US3] Ajouter dans `callbacks/tabs.py` le callback `filter_dispositifs` :
  `Input("filter-connexion","value")` + `Input("filter-batterie","value")` +
  `Input("filter-projet-multi","value")` → `Output("table-dispositifs","data")` +
  `Output("table-dispositifs","columns")`. Filtrage Python sur les données du cache.
- [X] T029 [US3] Ajouter dans `callbacks/tabs.py` le callback `show_device_detail` :
  `Input("table-dispositifs","selected_rows")` → `Output("modal-dispositif","is_open")` +
  `Output("modal-dispositif-content","children")`. Créer le composant `dbc.Modal` ou `html.Div`
  avec id `modal-dispositif` dans `ui/tabs/dispositifs.py`. Afficher toutes les métadonnées
  disponibles du dispositif sélectionné.

**Checkpoint US3**: Table filtrée et triable opérationnelle. Modal détail s'ouvre au clic.

---

## Phase 6 : User Story 4 — Consultation projets et scores (Priority: P2)

**Goal**: Onglet "Projets" fusionnant les anciens onglets Projets et Scores : cartes projet
avec score santé, filtres type/statut/recherche, détail avec graphe couverture et score qualité.

**Independent Test**: Filtrer "Actif" → seuls les projets actifs. Clic sur une carte → détail
avec score visible.

### Implémentation User Story 4

- [X] T030 [US4] Mettre à jour `ui/tabs/projets.py` : intégrer `render_scores()` (ancien contenu
  de `ui/tabs/scores.py`) directement dans `render_projets()`. Les cartes de projet DOIVENT
  afficher : nom, code, dates, dispositifs actifs/total, score santé (depuis collection `scores`
  via cache), statut calculé (Actif / Se termine bientôt / Archivé). Ne pas importer
  `ui/tabs/scores.py` (fichier supprimé en T012).
- [X] T031 [P] [US4] Ajouter dans `ui/tabs/projets.py` les filtres :
  - `dcc.Input(id="search-projet", placeholder="Rechercher...", debounce=True)`
  - `dcc.Dropdown(id="filter-type-projet")` (types de projets depuis le cache)
  - `dcc.RadioItems(id="filter-statut-projet", options=["Tous","Actif","Se termine bientôt","Archivé"])`
- [X] T032 [US4] Ajouter dans `callbacks/tabs.py` le callback `filter_projets` :
  `Input("search-projet","value")` + `Input("filter-type-projet","value")` +
  `Input("filter-statut-projet","value")` → `Output("projets-container","children")`. Filtrage
  Python sur le cache.
- [X] T033 [US4] Implémenter le détail projet dans `ui/tabs/projets.py` : composant expandable
  ou modal montrant description, liste des dispositifs attachés, graphe couverture temporelle
  (depuis collection `schedule` du cache), score qualité détaillé (depuis collection `scores`
  du cache).

**Checkpoint US4**: Cartes projets + filtres + détail avec score et graphe couverture.

---

## Phase 7 : User Story 5 — Gestion des alertes (Priority: P3)

**Goal**: Onglet "Gestion des Alertes" affichant l'historique `alert_history` (lecture seule),
le statut service alerter, le formulaire de seuils migré depuis la sidebar, et la route webhook
Mailgun HMAC.

**Independent Test**: Avec entrées dans `alert_history`, table visible avec 50 dernières alertes.
Modification d'un seuil → valeur persistée dans `store-seuils`. Requête webhook avec signature
invalide → 403.

### Implémentation User Story 5

- [X] T034 [US5] Créer `ui/tabs/alertes.py` : implémenter `render_alertes(data)` avec :
  (a) Table des 50 dernières alertes depuis `alert_history` (requête directe MongoDB lecture
  seule via `get_client()`, pas depuis le cache principal) — colonnes : date/heure, sujet,
  nb problèmes, destinataires, statut Mailgun (envoyé/livré/bounced/échoué), id `table-alertes` ;
  (b) Section statut service alerter : dernier cycle d'analyse (depuis `alert_history` dernière
  entrée), nb problèmes actifs (depuis cache), prochaine exécution (calculée depuis PM2 cron si
  disponible, sinon "N/A") ;
  (c) Formulaire seuils : 3 inputs `dcc.Input(id="seuil-battery")`, `dcc.Input(id="seuil-ending")`,
  `dcc.Input(id="seuil-activity")` + bouton "Enregistrer" `id="btn-save-seuils"`. Ces IDs sont
  IDENTIQUES à ceux de `ui/sidebar.py` (supprimé) — le callback `save_seuils` dans
  `callbacks/auth.py` fonctionne sans modification.
- [X] T035 [P] [US5] Vérifier que `callbacks/auth.py` — callback `save_seuils` fonctionne sans
  modification maintenant que les inputs sont dans `ui/tabs/alertes.py` : le store `store-seuils`
  structure `{bt, ed, am, pd}` est inchangé. Si le callback génère des erreurs (composants absents
  avant rendu de l'onglet), ajouter `prevent_initial_call=True`.
- [X] T036 [US5] Implémenter `POST /unifield/mailgun-webhook` dans `auth/routes.py` (ou `app.py`) :
  (a) Extraire `timestamp`, `token`, `signature` du payload Mailgun ;
  (b) Calculer `expected = HMAC-SHA256(key=MAILGUN_WEBHOOK_SIGNING_KEY, msg=(timestamp+token))` ;
  (c) Si `expected != signature` → retourner 403 immédiatement sans log détaillé ;
  (d) Si valide : mettre à jour `mailgun_status` dans `alert_history` (match sur `message-id`) ;
  (e) Logger structuré : `{"event": "mailgun_webhook", "type": "<event>", "ts": "..."}`.
  La clé `MAILGUN_WEBHOOK_SIGNING_KEY` ne doit jamais apparaître dans les logs.

**Checkpoint US5**: Table alertes lisible, seuils modifiables, webhook 403 sur signature invalide.

---

## Phase 8 : Polish et transversal

**Objectif**: Charte visuelle Z42, configuration réseau/PM2, recette staging complète.

- [X] T037 [P] Mettre à jour `assets/custom.css` : appliquer la charte dark cyber Z42.
  Variables CSS obligatoires : `--accent: #7DC242`, `--bg: #0a0a0a`, `--bg-card: #111`,
  `--text: #e0e0e0`, `--border: #333`. Styler : header fixe (fond `#0a0a0a`, border-bottom accent),
  boutons onglets (actif = accent, inactif = fond sombre), KPIs (fond card), indicateur MongoDB
  (vert = `#7DC242`, rouge = `#e53935`), tables (fond sombre, lignes alternées). Appliquer à
  toutes les classes générées par Dash.
- [X] T038 [P] Créer `ecosystem.config.js` à la racine du projet SMSI (ou dans le répertoire
  unifield) : définir 2 process PM2 :
  - `unifield-dashboard` : script gunicorn, args `app:server --workers 1 --threads 4 --bind 0.0.0.0:<PORT>`,
    env `APP_ENV=production`, `cwd` pointant vers le répertoire unifield
  - `unifield-alerter` : script python, args `alerter.py`, env `APP_ENV=production`
- [ ] T039 [P] Documenter (ou patcher) la configuration nginx : s'assurer que le bloc
  `location /unifield/` utilise `proxy_pass http://127.0.0.1:<PORT>/unifield/` (pass-through sans
  strip). Ne PAS passer le header `X-User-Email`. Consigner la config dans
  `specs/001-unifield-smsi-migration/contracts/flask-routes.md` si elle n'est pas déjà à jour.
- [ ] T040 Exécuter la checklist de recette staging complète (11 points de `quickstart.md`) en
  environnement staging. Documenter chaque point (✅ / ❌) dans
  `specs/001-unifield-smsi-migration/progress-log.md` (ACTION-025).
- [ ] T041 [P] Mettre à jour `specs/001-unifield-smsi-migration/progress-log.md` : remplir toutes
  les entrées des phases 1 à 7 (Actions 011 à 024) avec les dates, résultats et auteurs réels.
- [X] T042 [P] Vérification sécurité finale :
  `grep -r "UNIFIELD_MONGO_URI\|AUTH_API.*SECRET\|MAILGUN_API_KEY\|MAILGUN_WEBHOOK" . --include="*.py" --include="*.js"`
  → Résultat attendu : uniquement des références à `config.*` ou `os.environ`, jamais des valeurs.
  Logger le résultat dans `progress-log.md`.

---

## Dépendances et ordre d'exécution

### Dépendances entre phases

- **Setup (Phase 1)** : Aucune dépendance — peut démarrer immédiatement
- **Foundational (Phase 2)** : Dépend de Phase 1 — BLOQUE toutes les user stories
- **US1 Auth SSO (Phase 3)** : Dépend de Phase 2 — BLOQUE l'accès à toutes les autres stories en production
- **US2 Tableau de bord (Phase 4)** : Dépend de Phase 2 (cache MongoDB) + Phase 3 (auth)
- **US3 Dispositifs (Phase 5)** : Dépend de Phase 2 + Phase 3 — peut commencer en parallèle de Phase 4
- **US4 Projets (Phase 6)** : Dépend de Phase 2 + Phase 3 — peut commencer en parallèle de Phase 4/5
- **US5 Alertes (Phase 7)** : Dépend de Phase 2 + Phase 3 + T009 (alerter.py) — indépendant de Phase 4/5/6
- **Polish (Phase 8)** : Dépend de toutes les phases précédentes désirées

### Dépendances par user story

- **US1 (P1)** : Aucune dépendance sur d'autres user stories. Peut commencer dès Phase 2 complète.
- **US2 (P1)** : Peut commencer dès US1 complète.
- **US3 (P2)** : Peut commencer dès US1 complète — indépendante de US2.
- **US4 (P2)** : Peut commencer dès US1 complète — indépendante de US2/US3.
- **US5 (P3)** : Peut commencer dès US1 + T009 complètes — indépendante de US2/US3/US4.

### Opportunités de parallélisation

- T002, T003 : parallèles entre eux (Phase 1)
- T005, T009, T011, T012 : parallèles entre eux dans Phase 2 (fichiers distincts)
- T013, T014, T015 : parallèles entre eux (Phase 3, fichiers auth distincts)
- T020, T021 : parallèles (tests indépendants)
- T026, T031 : parallèles dans leurs phases respectives
- T037, T038, T039, T041, T042 : tous parallèles en Phase 8

---

## Exemples de parallélisation par user story

```bash
# Phase 2 — Foundational (lancer en parallèle après T004):
Tâche: "Créer api/mongo_client.py (T004)"
↓ complétée →
Tâche A: "Créer api/mongo_loader.py (T006)"           # 1er développeur
Tâche B: "Modifier alerter.py alert_history (T009)"   # 2ème développeur
Tâche C: "Modifier ui/layout.py header SMSI (T010)"   # 3ème développeur

# Phase 3 — US1 Auth (lancer en parallèle après Phase 2):
Tâche A: "auth/role_check.py + tests (T013, T020)"
Tâche B: "auth/session_store.py + tests (T014, T021)"
Tâche C: "auth/session_cookie.py (T015)"

# Phases 5/6/7 — US3/US4/US5 (lancer en parallèle après US1):
Tâche A: "ui/tabs/dispositifs.py (T026→T029)"
Tâche B: "ui/tabs/projets.py fusion (T030→T033)"
Tâche C: "ui/tabs/alertes.py (T034→T036)"
```

---

## Stratégie d'implémentation

### MVP (US1 + US2 uniquement)

1. Compléter Phase 1 : Setup
2. Compléter Phase 2 : Foundational
3. Compléter Phase 3 : US1 (Auth SSO)
4. **STOP et VALIDER** : login Microsoft, 403 sans rôle, pytest vert
5. Compléter Phase 4 : US2 (Tableau de bord)
6. **STOP et VALIDER** : urgences affichées, graphe snapshots après 30 min
7. Déployer MVP en staging

### Livraison incrémentale

1. MVP (Phase 1→4) → recette partielle → staging
2. Ajouter US3 (Dispositifs) → tester indépendamment
3. Ajouter US4 (Projets) → tester indépendamment
4. Ajouter US5 (Alertes) → tester indépendamment
5. Phase 8 (Polish + réseau) → recette complète

---

## Notes

- `[P]` = fichiers distincts, aucune dépendance sur une tâche incomplète de la même phase
- `[USn]` = user story de référence pour la traçabilité
- Chaque checkpoint valide l'user story de façon indépendante
- Commiter après chaque phase ou checkpoint (utiliser `/speckit-git-commit`)
- Mettre à jour `progress-log.md` à chaque action complétée
- Arrêter à chaque checkpoint pour valider avant de continuer

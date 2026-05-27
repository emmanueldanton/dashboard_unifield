# Journal d'actions — Migration UNIFIELD Console SMSI CAD.42

**Branche**: `001-unifield-smsi-migration`
**Objectif**: Tracer chaque action effectuée pendant la migration pour générer un rapport de fin
de projet.

---

## Format d'entrée

Chaque action est consignée ainsi :

```
### ACTION-NNN — [Titre court]
- **Date** : YYYY-MM-DD HH:MM
- **Phase** : Phase N — [Nom]
- **Fichier(s)** : chemin/vers/fichier.py
- **Type** : CRÉÉ | MODIFIÉ | SUPPRIMÉ | VALIDÉ | RENOMMÉ | TESTÉ | DÉPLOYÉ
- **Auteur** : [nom ou "Claude Code"]
- **Détail** : Description de ce qui a été fait et pourquoi.
- **Résultat** : ✅ Succès | ⚠️ Partiel | ❌ Échec — [détail si non-succès]
```

---

## Phase 0 — Prérequis externes

### ACTION-001 — Constitution du projet rédigée
- **Date** : 2026-05-26
- **Phase** : Phase 0 — Prérequis / Gouvernance
- **Fichier(s)** : `.specify/memory/constitution.md`
- **Type** : CRÉÉ
- **Auteur** : Claude Code
- **Détail** : Constitution UNIFIELD CAD.42 v1.0.0 ratifiée avec 9 principes non-négociables
  (proportionnalité, auth déléguée, MongoDB read-only, cache obligatoire, iso-interface, layout SMSI,
  séparation process, secrets hors code, stack minimal). Conformité ISO 27001:2022 documentée.
- **Résultat** : ✅ Succès

### ACTION-002 — Spécification feature rédigée (27 FR, 5 US, 8 SC)
- **Date** : 2026-05-26
- **Phase** : Phase 0 — Spécification
- **Fichier(s)** : `specs/001-unifield-smsi-migration/spec.md`
- **Type** : CRÉÉ
- **Auteur** : Claude Code
- **Détail** : Spec complète — 5 user stories (P1→P3), 28 exigences fonctionnelles (FR-001 à
  FR-028), 9 critères de succès mesurables, edge cases, entités clés, hypothèses.
- **Résultat** : ✅ Succès

### ACTION-003 — Branche git feature créée
- **Date** : 2026-05-26
- **Phase** : Phase 0 — Initialisation
- **Fichier(s)** : *(branche git)*
- **Type** : CRÉÉ
- **Auteur** : Claude Code / speckit-git-feature
- **Détail** : Branche `001-unifield-smsi-migration` créée depuis `main`.
- **Résultat** : ✅ Succès

### ACTION-004 — 13 clarifications architecturales encodées dans spec.md
- **Date** : 2026-05-26
- **Phase** : Phase 0 — Clarification
- **Fichier(s)** : `specs/001-unifield-smsi-migration/spec.md`
- **Type** : MODIFIÉ
- **Auteur** : Claude Code
- **Détail** : 13 décisions techniques encodées (MongoClient pool params, cache singleton clé fixe,
  active-tab store, callback snapshots isolé, HMAC webhook, before_request dual condition, seuils
  store-seuils, dégradation gracieuse, migration onglets). FR-028 ajouté. SC-009 ajouté.
- **Résultat** : ✅ Succès

### ACTION-005 — Plan d'implémentation rédigé
- **Date** : 2026-05-26
- **Phase** : Phase 0 — Planification
- **Fichier(s)** : `specs/001-unifield-smsi-migration/plan.md`
- **Type** : CRÉÉ
- **Auteur** : Claude Code
- **Détail** : Plan complet — contexte technique, constitution check (9/9 ✅), structure source
  code (nouveaux/modifiés/conservés/retirés), phasage 0→5 avec chemin critique, tableau de
  validation.
- **Résultat** : ✅ Succès

### ACTION-006 — Research.md : 13 décisions architecturales documentées
- **Date** : 2026-05-26
- **Phase** : Phase 0 — Recherche
- **Fichier(s)** : `specs/001-unifield-smsi-migration/research.md`
- **Type** : CRÉÉ
- **Auteur** : Claude Code
- **Détail** : 13 décisions (D-001 à D-013) avec décision, rationale et alternatives rejetées.
- **Résultat** : ✅ Succès

### ACTION-007 — Data model documenté (collections Mongo + structures cache)
- **Date** : 2026-05-26
- **Phase** : Phase 1 — Modèle de données
- **Fichier(s)** : `specs/001-unifield-smsi-migration/data-model.md`
- **Type** : CRÉÉ
- **Auteur** : Claude Code
- **Détail** : Schémas de toutes les collections MongoDB (projets, trackers, units, events,
  schedule, scores, snapshots, alert_history), structure CacheServeur, stores Dash (active-tab,
  conn-status, store-seuils), session utilisateur.
- **Résultat** : ✅ Succès

### ACTION-008 — Contrats routes auth (/auth/*) documentés
- **Date** : 2026-05-26
- **Phase** : Phase 1 — Contrats
- **Fichier(s)** : `specs/001-unifield-smsi-migration/contracts/auth-routes.md`
- **Type** : CRÉÉ
- **Auteur** : Claude Code
- **Détail** : Contrats HTTP pour /auth/login, /auth/complete, /auth/logout, /auth/me + middleware
  before_request + spécification cookie unifield.sid.
- **Résultat** : ✅ Succès

### ACTION-009 — Contrat route /mailgun-webhook documenté
- **Date** : 2026-05-26
- **Phase** : Phase 1 — Contrats
- **Fichier(s)** : `specs/001-unifield-smsi-migration/contracts/flask-routes.md`
- **Type** : CRÉÉ
- **Auteur** : Claude Code
- **Détail** : Contrat HTTP POST /unifield/mailgun-webhook avec vérification HMAC-SHA256 +
  configuration nginx pass-through + configuration PM2.
- **Résultat** : ✅ Succès

### ACTION-010 — Guide quickstart développeur rédigé
- **Date** : 2026-05-26
- **Phase** : Phase 1 — Documentation développeur
- **Fichier(s)** : `specs/001-unifield-smsi-migration/quickstart.md`
- **Type** : CRÉÉ
- **Auteur** : Claude Code
- **Détail** : Guide de démarrage — variables d'environnement, installation, démarrage dev, commandes
  de validation iso-interface, tests pytest, checklist de recette staging (11 points).
- **Résultat** : ✅ Succès

---

## Phase 1 — MongoDB

### ACTION-011 — Création api/mongo_client.py
- **Date** : 2026-05-26 00:00
- **Phase** : Phase 1 — MongoDB
- **Fichier(s)** : `api/mongo_client.py`
- **Type** : CRÉÉ
- **Auteur** : Claude Code
- **Détail** : Singleton `get_db()` post-fork safe avec double-checked locking. Paramètres pool
  obligatoires : `maxPoolSize=20`, `minPoolSize=3`, `connectTimeoutMS=10000`,
  `socketTimeoutMS=15000`, `maxIdleTimeMS=60000`. URI depuis `config.UNIFIELD_MONGO_URI`,
  jamais loggée. Package `api/` initialisé avec `__init__.py`.
- **Résultat** : ✅ Succès

### ACTION-012 — Création api/mongo_loader.py
- **Date** : 2026-05-26 00:00
- **Phase** : Phase 1 — MongoDB
- **Fichier(s)** : `api/mongo_loader.py`
- **Type** : CRÉÉ
- **Auteur** : Claude Code
- **Détail** : `load_all_data()` implémentant le chargement 2-temps : (1) projets + trackers pour
  tous les projets ; (2) units, events, schedule, scores uniquement pour les projets actifs
  (`archived=False AND endDate > utcnow()`). Association tracker→projet en Python (pas `$lookup`).
  Couche d'adaptation des champs battery (`lastTrack.message.battery_volt`). Enrichissements
  `_is_connected`, `_battery_volt`, `_project_name` identiques à `api/loader.py`. Retourne les
  mêmes clés que l'API REST : `projects`, `project_data`, `all_units`, `all_trackers`,
  `all_events`, `qc`, `loaded_at`.
- **Résultat** : ✅ Succès

### ACTION-013 — Refacto cache.py (mongo_loader + save_snapshot)
- **Date** : 2026-05-26 00:00
- **Phase** : Phase 1 — MongoDB
- **Fichier(s)** : `cache.py`
- **Type** : MODIFIÉ
- **Auteur** : Claude Code
- **Détail** : (a) Import dynamique `api.mongo_loader` si `UNIFIELD_SOURCE=="mongo"`, fallback
  `api.loader` si `"rest"`. (b) Clé cache fixe interne (suppression de la clé `md5(email:key)`) —
  signatures `get_cached_data(email, key)` et `set_cached_data(email, key, data)` conservées.
  (c) `save_snapshot(project_data)` invoquée une seule fois à la fin de `_do_refresh` : insère
  `{project_id, ts, connected, disconnected, battery_low}` dans la collection `snapshots`.
  Échec d'insertion logguée silencieusement, cache continue. `_mongo_ok` et `_last_success`
  mis à jour dans le dict de cache.
- **Résultat** : ✅ Succès

### ACTION-014 — Validation iso-interface (diff ref_rest vs ref_mongo)
- **Date** :
- **Phase** : Phase 1 — Validation
- **Fichier(s)** : `specs/001-unifield-smsi-migration/ref_rest.json`, `ref_mongo.json`
- **Type** : VALIDÉ
- **Auteur** :
- **Détail** : T005 (génération ref_rest.json) et T007 (diff iso-interface) bloqués sur accès
  à l'API REST live en environnement staging. À réaliser lors de la recette staging (T040).
- **Résultat** : ⚠️ Partiel — en attente staging

### ACTION-015 — alerter.py — écriture alert_history
- **Date** : 2026-05-26 00:00
- **Phase** : Phase 1 — MongoDB
- **Fichier(s)** : `alerter.py`
- **Type** : MODIFIÉ
- **Auteur** : Claude Code
- **Détail** : À chaque envoi Mailgun réussi, insertion d'un document
  `{ts, subject, issues_count, recipients, mailgun_status}` dans la collection `alert_history`
  via `get_client()` (pool identique à `api/mongo_client.py`). Logique d'alerte existante non
  modifiée. Log structuré : `{"event": "alert_sent", ...}`.
- **Résultat** : ✅ Succès

---

## Phase 2 — Auth SSO

### ACTION-016 — Création package auth/ (6 modules)
- **Date** : 2026-05-26 00:00
- **Phase** : Phase 2 — Auth SSO
- **Fichier(s)** : `auth/__init__.py`, `auth/role_check.py`, `auth/session_store.py`,
  `auth/session_cookie.py`, `auth/microsoft_flow.py`, `auth/routes.py`
- **Type** : CRÉÉ
- **Auteur** : Claude Code
- **Détail** : (1) `role_check.py` — `check_role(user_info)` retourne le premier rôle valide
  parmi `admin`, `app:unifield:admin`, `app:unifield:write`, `app:unifield:read` ; lève
  `NoUnifieldRoleError` sinon. (2) `session_store.py` — dict RAM `_sessions` avec clé
  `sha256(sid)`, TTL 24h, CRUD complet + `cleanup_expired()`. (3) `session_cookie.py` —
  cookie `unifield.sid` httpOnly, SameSite=Lax, secure si production. (4) `microsoft_flow.py` —
  `build_auth_url(state)` et `exchange_code(code, state)` vers auth-api ServiceConsumer
  `"unifield"` ; secret jamais loggé. (5) `routes.py` — Blueprint `/unifield/auth/` avec
  /login, /complete (403 NoUnifieldRoleError), /logout, /me. Route webhook Mailgun HMAC
  enregistrée dans ce même fichier.
- **Résultat** : ✅ Succès

### ACTION-017 — before_request + routes auth enregistrées dans app.py
- **Date** : 2026-05-26 00:00
- **Phase** : Phase 2 — Auth SSO
- **Fichier(s)** : `app.py`
- **Type** : MODIFIÉ
- **Auteur** : Claude Code
- **Détail** : (a) Ajout `requests_pathname_prefix="/unifield/"` et
  `routes_pathname_prefix="/unifield/"`. (b) Blueprint `auth.routes` enregistré sur `app.server`.
  (c) Route POST `/unifield/mailgun-webhook` enregistrée. (d) `@app.server.before_request` :
  passe les routes `/unifield/auth/*` et `/unifield/mailgun-webhook` ; bypass double condition
  `UNIFIELD_DEV_AUTH_BYPASS=true AND APP_ENV != production` ; sinon vérifie session RAM et
  redirige 302 vers /auth/login. `suppress_callback_exceptions=True` activé.
- **Résultat** : ✅ Succès

### ACTION-018 — Tests pytest auth/role_check + auth/session_store
- **Date** : 2026-05-26 00:00
- **Phase** : Phase 2 — Validation
- **Fichier(s)** : `tests/test_role_check.py`, `tests/test_session_store.py`
- **Type** : TESTÉ
- **Auteur** : Claude Code
- **Détail** : 13 tests créés et exécutés — 7 dans `test_role_check.py` (admin, unifield:admin,
  read, write, no role, non-unifield role, priority order) et 6 dans `test_session_store.py`
  (create, get, get unknown, delete, cleanup expired, get expired returns None).
  Commande : `pytest tests/test_role_check.py tests/test_session_store.py -v`
- **Résultat** : ✅ Succès — 13/13 passed

---

## Phase 3 — Refonte Layout

### ACTION-019 — Nouveau header SMSI dans ui/layout.py
- **Date** : 2026-05-26 00:00
- **Phase** : Phase 3 — Layout
- **Fichier(s)** : `ui/layout.py`
- **Type** : MODIFIÉ
- **Auteur** : Claude Code
- **Détail** : Suppression de l'import `ui/sidebar.py`. Header horizontal fixe créé avec :
  titre "Tableau de bord opérationnel UNIFIELD — CAD.42", email utilisateur (depuis
  `store-creds`), date/heure dernier refresh, indicateur MongoDB (`conn-status-indicator`),
  bouton "Actualiser" (`btn-refresh`), rangée 5 KPIs (`kpi-bar`), 4 boutons onglet
  (`btn-tab-dashboard`, `btn-tab-dispositifs`, `btn-tab-projets`, `btn-tab-alertes`).
  Stores ajoutés : `active-tab`, `conn-status`. Intervals : `interval-15min` (900000ms) et
  `interval-ui` (1000ms, disabled). `dcc.Location(id="url")` ajouté.
- **Résultat** : ✅ Succès

### ACTION-020 — 4 nouveaux onglets (callbacks/tabs.py + ui/tabs/*)
- **Date** : 2026-05-26 00:00
- **Phase** : Phase 3 — Layout
- **Fichier(s)** : `callbacks/tabs.py`, `ui/tabs/dashboard.py`, `ui/tabs/dispositifs.py`,
  `ui/tabs/projets.py`, `ui/tabs/alertes.py`
- **Type** : CRÉÉ / MODIFIÉ
- **Auteur** : Claude Code
- **Détail** : 4 modules UI créés/étendus. `callbacks/tabs.py` totalement réécrit avec 8
  callbacks : navigation onglets, rendu tab-content, CSS boutons actifs, filtre snapshots MongoDB
  (go.Scatter, 3 séries), filtre dispositifs (connexion/batterie/projet multi-select),
  modal détail dispositif, fermeture modal clientside, filtre projets (recherche/type/statut).
  `callbacks/auth.py` étendu avec callback `load_creds` (SSO session → store-creds) et
  `save_seuils`. `callbacks/modals.py` : `creds["key"]` → `creds.get("key", "")` pour
  compatibilité nouveau format store-creds.
- **Résultat** : ✅ Succès

### ACTION-021 — Suppression sidebar + fichiers retirés
- **Date** : 2026-05-26 00:00
- **Phase** : Phase 3 — Layout
- **Fichier(s)** : `ui/sidebar.py`, `ui/tabs/scores.py`, `ui/tabs/qc.py`
- **Type** : SUPPRIMÉ
- **Auteur** : Claude Code
- **Détail** : Vérification préalable des imports résiduels dans tout le code (aucun trouvé
  après refactoring). Logique `render_scores()` intégrée directement dans `ui/tabs/projets.py`.
  Logique QC supprimée (onglet QC retiré du plan). `ui/sidebar.py` retiré (formulaire email/key
  remplacé par SSO). 3 fichiers supprimés via `git rm`.
- **Résultat** : ✅ Succès

### ACTION-022 — interval-15min + callback snapshots isolé
- **Date** : 2026-05-26 00:00
- **Phase** : Phase 3 — Layout / Refresh
- **Fichier(s)** : `callbacks/sync.py`, `callbacks/tabs.py`
- **Type** : MODIFIÉ
- **Auteur** : Claude Code
- **Détail** : `callbacks/sync.py` : `interval-15min` branché sur `force_refresh` qui met à
  jour `conn-status` `{ok, last_success}` ; dégradation gracieuse si MongoDB échoue (cache
  conservé, `ok=False`, log structuré `mongo_refresh_failed`) ; KPIs calculés et émis vers
  `kpi-bar`. `interval-ui` (1s) sans output partagé avec `interval-15min`. Callback snapshots
  MongoDB dans `callbacks/tabs.py` : lecture directe collection `snapshots`, figure go.Scatter
  3 séries, plages 6h/24h/7j, annotation si vide.
- **Résultat** : ✅ Succès

---

## Phase 4 — Réseau / PM2

### ACTION-023 — config.py + ecosystem.config.js + nginx
- **Date** : 2026-05-26 00:00
- **Phase** : Phase 4 — Réseau / PM2
- **Fichier(s)** : `config.py`, `ecosystem.config.js`, `specs/.../contracts/flask-routes.md`
- **Type** : MODIFIÉ / CRÉÉ
- **Auteur** : Claude Code
- **Détail** : `config.py` : ajout de `UNIFIELD_MONGO_URI`, `UNIFIELD_MONGO_DB`,
  `BASE_PATH="/unifield/"`, `PUBLIC_URL`, `APP_ENV`, `UNIFIELD_SOURCE`, `AUTH_API_URL`,
  `AUTH_API_SERVICE_CONSUMER_SECRET`, `UNIFIELD_DEV_AUTH_BYPASS`. Lecture `os.environ` avec
  `python-dotenv`. `ecosystem.config.js` créé avec 2 processus PM2 (`unifield-dashboard`
  gunicorn 1 worker 4 threads, `unifield-alerter` python3). Config nginx pass-through
  `/unifield/` documentée dans `contracts/flask-routes.md` (X-User-Email interdit).
- **Résultat** : ✅ Succès

---

## Phase 5 — Charte Z42

### ACTION-024 — Palette dark cyber assets/custom.css
- **Date** : 2026-05-26 00:00
- **Phase** : Phase 5 — Charte Z42
- **Fichier(s)** : `assets/custom.css`
- **Type** : MODIFIÉ
- **Auteur** : Claude Code
- **Détail** : Charte dark cyber Z42 complète. Variables CSS : `--accent: #7DC242`,
  `--bg: #0a0a0a`, `--bg-card: #111`, `--text: #e0e0e0`, `--border: #333`. Styles :
  header fixe (fond `#0a0a0a`, border-bottom accent), boutons onglets (actif = accent vert,
  inactif = fond sombre), KPIs (fond card), indicateur MongoDB (vert `#7DC242` / rouge
  `#e53935`), tables DataTable (fond sombre, lignes alternées), modals sombres.
  Overrides complets pour les classes Dash et Plotly générées.
- **Résultat** : ✅ Succès

### ACTION-026 — Refactoring chargement 2-phases (mongo_loader.py)
- **Date** : 2026-05-26 15:42
- **Phase** : Phase 9 — Optimisation loader MongoDB
- **Fichier(s)** : `api/mongo_loader.py`, `diag.py`
- **Type** : MODIFIÉ
- **Auteur** : Claude Code
- **Détail** : Refactoring complet de `api/mongo_loader.py` en chargement 2-phases.
  Phase 1 : toutes les 268 bases NNNN_* → trackers + lastTrack résolu + enrichissements business.
  Critère d'activité : `ACTIVE_TRACKER_SECONDS = 30` — tracker actif si lastUpdate < 30s.
  Phase 2 : 10 bases actives seulement → units, events, association tracker↔unit (mutation in-place).
  Résultats mesurés : 268 bases avec trackers, 10 actives, 258 inactives, 2514 trackers, 54 units.
  Temps de chargement : 13.8s (vs 37s avant refactoring, cible < 25s).
  Suppression de `_load_project_db()` remplacée par `_phase1_load_trackers()` + `_phase2_load_details()`.
- **Résultat** : ✅ Succès — temps < 25s, projets actifs identifiés correctement, associations unit/tracker OK

---

## Recette staging (à remplir lors de la validation finale)

### ACTION-025 — [À remplir] Recette staging complète (11 points checklist)
- **Date** :
- **Phase** : Validation finale
- **Fichier(s)** : `specs/001-unifield-smsi-migration/quickstart.md` (checklist)
- **Type** : VALIDÉ
- **Auteur** :
- **Détail** : Points 1 à 11 de la checklist de recette staging.
- **Résultat** :

---

## Template rapport final

> À compléter en fin de migration depuis les entrées ci-dessus.

```
# Rapport de migration — Dashboard UNIFIELD Console SMSI CAD.42

**Date de fin** : YYYY-MM-DD
**Branche** : 001-unifield-smsi-migration
**Phases complètes** : Phase 0 ✅ | Phase 1 [?] | Phase 2 [?] | Phase 3 [?] | Phase 4 [?] | Phase 5 [?]

## Actions réalisées : XX / 25
## Actions en succès : XX
## Actions partielles : XX
## Actions échouées : XX

## Fichiers créés : [liste depuis progress-log]
## Fichiers modifiés : [liste]
## Fichiers supprimés : [liste]

## Validation iso-interface : ✅ / ❌
## Tests pytest : ✅ / ❌
## Recette staging : ✅ / ❌

## Incidents rencontrés
[À compléter]

## Non-conformités constitutionnelles
[Aucune / ou lister avec justification]
```

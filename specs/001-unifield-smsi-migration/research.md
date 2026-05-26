# Research: Migration UNIFIELD — Console SMSI CAD.42

**Branch**: `001-unifield-smsi-migration` | **Date**: 2026-05-26

Toutes les décisions architecturales ont été fournies directement par le CTO/RSSI (Emmanuel Danton)
dans la description de feature et les 13 clarifications. Aucun NEEDS CLARIFICATION n'est resté ouvert.
Ce document consolide les décisions et leur rationale.

---

## D-001 — Source de données : MongoDB Atlas via iso-interface

**Décision** : Remplacer `api/loader.py` + `api/client.py` par `api/mongo_loader.py` qui expose la
même interface de sortie (`load_all_data()` → dict avec clés `projects`, `project_data`, `all_units`,
`all_trackers`, `all_events`, `qc`, `loaded_at`).

**Rationale** : Garantit que `business/` et tous les callbacks existants fonctionnent sans
modification (principe V constitution — Iso-interface). La couche d'adaptation des champs (ex.
`battery` plat → `lastTrack.message.battery_volt`) est entièrement dans `mongo_loader.py`.

**Alternatives considérées** :
- Modifier `business/trackers.py` pour accepter les deux formats → rejeté (viole principe V)
- Patcher les callbacks un par un → rejeté (risque de régression élevé, non maintenable)

**Validation** : Diff structurel `load_all_data()` vs jeu de référence REST figé. Zéro écart
de champ ou d'enrichissement `_*` toléré.

---

## D-002 — MongoClient singleton avec création lazy post-fork

**Décision** : `api/mongo_client.py` expose `get_client()` qui crée l'instance `MongoClient`
au premier appel dans le worker (jamais au niveau module). Paramètres de pool :
`maxPoolSize=20`, `minPoolSize=3`, `connectTimeoutMS=10000`, `socketTimeoutMS=15000`,
`maxIdleTimeMS=60000`.

**Rationale** : Gunicorn forke les workers après l'import du module. Un `MongoClient` créé au
niveau module serait partagé par tous les workers via `fork()`, ce qui corrompt les descripteurs
de socket. La création lazy post-fork évite ce problème. Avec `--workers 1`, ce risque est
théorique mais la bonne pratique s'applique pour garantir la compatibilité future.

**Alternatives considérées** :
- Connexion par requête → rejeté (overhead réseau, viole principe IV)
- `fork_safe=True` pymongo → disponible mais pattern lazy plus lisible et standard

---

## D-003 — Cache singleton, suppression de la clé `md5(email:key)`

**Décision** : La clé `md5(email:key)` est supprimée. `get_cached_data(email, key)` conserve sa
signature pour compatibilité avec les callbacks existants mais ignore les arguments en interne
(clé fixe unique par process). Le cache est partagé par tous les utilisateurs connectés.

**Rationale** : En production SSO, l'authentification est vérifiée par `before_request` avant tout
accès au cache. Le cache contient des données métier (non personnelles) accessibles à tous les rôles
`app:unifield:*`. Une clé par utilisateur est inutile et complexifiait le code sans bénéfice de
sécurité (principe I — proportionnalité).

**Alternatives considérées** :
- Conserver la clé md5 en ajoutant l'email SSO → ajout de complexité sans bénéfice
- Redis comme store de cache partagé → hors stack autorisé (principe IX)

---

## D-004 — Authentification : before_request sur app.server, double condition bypass

**Décision** : Un décorateur `@app.server.before_request` inspecte toutes les requêtes entrantes.
Sans session valide : HTML → 302 `/unifield/auth/login`, JSON → 401. Le bypass dev est activé
uniquement si `UNIFIELD_DEV_AUTH_BYPASS=true` ET `APP_ENV != production` sont simultanément vrais.

**Rationale** : `before_request` est le seul point de contrôle universel pour une app Dash —
les callbacks Dash ne sont pas des routes Flask ordinaires. La double condition `bypass` empêche
une activation accidentelle en staging ou production via une seule variable mal positionnée.

**Alternatives considérées** :
- Décorateur par callback → non applicable (Dash ne supporte pas la décoration de callback)
- Middleware WSGI externe → hors stack autorisé, plus complexe à tester

---

## D-005 — Package auth/ : portage de role-check.js, session-store.js, session-cookie.js

**Décision** : Le package `auth/` reproduit en Python les abstractions SSO déjà existantes dans le
monorepo SMSI (côté Node). Chaque module est indépendant et testable unitairement :
- `role_check.py` : lève `NoUnifieldRoleError` si aucun rôle valide
- `session_store.py` : dict RAM avec TTL cleanup, sha256(sid) comme clé
- `session_cookie.py` : lecture/écriture cookie `unifield.sid` httpOnly SameSite=Lax Secure
- `microsoft_flow.py` : échange code OAuth2 contre token via auth-api
- `routes.py` : Blueprint Flask enregistré sur `app.server`

**Rationale** : Réutiliser les patterns éprouvés du monorepo SMSI réduit les risques de régression
de sécurité. L'isolation dans un package `auth/` respecte la séparation des couches (mapping rôles
uniquement dans `role_check.py`, principe constitution — gouvernance technique).

**Alternatives considérées** :
- Intégrer auth dans `app.py` directement → non maintenable, viole séparation des couches
- Bibliothèque Flask-Login → hors stack autorisé (principe IX)

---

## D-006 — Collection snapshots : write par dashboard, read par Onglet 1

**Décision** : `cache.py` appelle `save_snapshot(project_data)` une seule fois à la fin de
`_do_refresh`, jamais depuis un callback. Échec silencieux (log + continue). Structure :
`{ project_id, ts, connected, disconnected, battery_low }`.

**Rationale** : Séparer l'écriture des snapshots du flux de rendu des callbacks garantit qu'un
échec d'insertion n'interrompt pas l'affichage des données. L'invocation unique à la fin de
`_do_refresh` garantit qu'un seul snapshot est écrit par cycle (pas de doublons).

**Alternatives considérées** :
- Écriture depuis un callback Dash → viole principe IV (aucune opération Mongo depuis callback)
- Écriture dans alerter.py → mélange des responsabilités, viole principe VII

---

## D-007 — Graphe évolution : callback Dash dédié et isolé

**Décision** : Le callback graphe snapshots écoute uniquement `Input("project-selector", "value")`
et `Input("time-range-selector", "value")`. Il n'est pas déclenché par `interval-15min` sauf si
un nouveau snapshot existe pour le projet sélectionné (comparaison via `dcc.Store` ou timestamp
en mémoire).

**Rationale** : Évite de requêter MongoDB snapshots toutes les 15 min pour tous les projets,
ce qui serait disproportionné (principe I) et potentiellement coûteux en latence.

**Alternatives considérées** :
- Callback déclenché par interval-15min sans condition → requêtes inutiles
- Polling client-side (JS) → hors stack autorisé

---

## D-008 — Intervalles Dash : isolation stricte des outputs

**Décision** :
- `interval-15min` (id `interval-15min`, 900 000 ms, disabled=False) → déclenche `force_refresh`
  dans `callbacks/sync.py` uniquement.
- `interval-ui` (id `interval-ui`, 1 000 ms, disabled=True hors loading) → déclenche les
  callbacks d'animation uniquement.
- Aucun output partagé entre les deux intervals.

**Rationale** : Partager des outputs entre intervals crée des races conditions dans Dash (un seul
callback peut posséder un Output). La séparation stricte évite les conflits et clarifie le flux.

---

## D-009 — Webhook Mailgun : HMAC-SHA256 obligatoire

**Décision** : La route `/unifield/mailgun-webhook` calcule `HMAC-SHA256(timestamp + token)` avec
`MAILGUN_WEBHOOK_SIGNING_KEY` et compare à la signature fournie par Mailgun. Signature invalide
→ 403 sans log détaillé.

**Rationale** : Prévient les injections dans `alert_history` via des faux webhooks. Le 403 sans
log détaillé évite la fuite d'information (principe VIII — secrets hors code et conformité A.8.16).

---

## D-010 — Store `store-seuils` : structure inchangée {bt, ed, am, pd}

**Décision** : Les inputs `seuil-battery`, `seuil-ending`, `seuil-activity` migrent uniquement
de `ui/sidebar.py` vers `ui/tabs/alertes.py` dans le DOM. Le store `store-seuils` et le callback
`save_seuils` dans `callbacks/auth.py` ne changent pas.

**Rationale** : Modifier le store ou les IDs des inputs aurait nécessité de toucher `business/alerts.py`
(qui lit les seuils) et plusieurs callbacks. La migration HTML-only est le changement minimal
conforme au principe V (iso-interface étendue à l'UI).

---

## D-011 — Onglet `active-tab` : store comme unique source de vérité

**Décision** : `dcc.Store(id="active-tab", data="dashboard")`. Un seul callback reçoit les
4 `n_clicks` des boutons d'onglet et émet la valeur de l'onglet actif. La classe CSS `active`
est calculée par un callback distinct depuis `active-tab`, jamais directement depuis `n_clicks`.

**Rationale** : Conforme au principe constitution (gouvernance technique — dcc.Store seule source
de vérité). Évite les incohérences si un onglet est activé programmatiquement (depuis une URL
ou une notification d'urgence).

---

## D-012 — Dégradation gracieuse MongoDB

**Décision** : En cas d'échec refresh (timeout, connexion refusée) :
1. Cache existant conservé intégralement
2. `conn-status` store mis à jour : `{ok: false, last_success: "2026-05-26T14:30:00Z"}`
3. Header affiche icône rouge + horodatage dernier succès
4. Log structuré : `{"event": "mongo_refresh_failed", "error": "...", "ts": "..."}`
5. Retry au prochain cycle interval-15min (aucune intervention manuelle)

**Rationale** : Un dashboard opérationnel ne doit jamais crasher sur une panne réseau transitoire.
L'affichage des données précédentes avec un indicateur clair est préférable à une page d'erreur
(proportionnalité + conformité A.8.16).

---

## D-013 — Migration de contenu des onglets supprimés

**Décision** :
- `tab-urgences` → `ui/tabs/dashboard.py` (Onglet 1) via `render_urgences()` conservé
- `tab-scores` → `ui/tabs/projets.py` (Onglet 3) via `render_scores()` intégré
- `tab-capteurs` → `ui/tabs/dispositifs.py` (Onglet 2) via `render_capteurs()` renommé
- `tab-qc` → supprimé (contenu non repris)
- `ui/tabs/scores.py` et `ui/tabs/qc.py` retirés du dépôt

**Rationale** : La qualité des données (ex-tab-qc) n'est plus pertinente avec MongoDB Atlas
(données structurées validées à l'insertion). La suppression allège le codebase
(principe I — proportionnalité).

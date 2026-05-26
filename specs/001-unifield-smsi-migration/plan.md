# Implementation Plan: Migration UNIFIELD — Console SMSI CAD.42

**Branch**: `001-unifield-smsi-migration` | **Date**: 2026-05-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-unifield-smsi-migration/spec.md`

## Summary

Migration du Dashboard UNIFIELD existant (source REST, auth formulaire email/clé, sidebar + 5
onglets) vers la 5ᵉ console opérationnelle du monorepo SMSI CAD.42. La migration porte sur trois
axes indépendants et partiellement parallélisables : (1) remplacement de la source de données REST
par MongoDB Atlas via une couche `api/mongo_loader.py` iso-interface, (2) remplacement du formulaire
d'authentification par SSO Microsoft Entra ID délégué à auth-api (ServiceConsumer), (3) refonte du
layout — suppression sidebar, nouveau header SMSI horizontal, 4 onglets. La logique métier
(`business/`) est préservée intacte. L'app reste servie par Gunicorn (1 worker, 4 threads) derrière
nginx sous le préfixe `/unifield/`, supervisée par PM2 dans le monorepo SMSI.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: Dash 2.17, Plotly 5.21, pymongo (dernière stable ≥ 4.x), gunicorn 22,
requests, python-dotenv
**Storage**: MongoDB Atlas — lecture seule sur `projects`, `trackers`, `units`, `events`, `schedule`,
`scores` ; lecture+écriture sur `snapshots` (dashboard) et `alert_history` (alerter.py uniquement)
**Testing**: pytest (auth/role_check, auth/session_store) + recette manuelle staging
**Target Platform**: Ubuntu VM Azure, nginx (pass-through `/unifield/`), PM2 (monorepo SMSI)
**Project Type**: Dashboard opérationnel — web application Dash/Python, single-process Gunicorn
**Performance Goals**: Accès post-SSO < 3 s ; cycle refresh 15 min ± 5 s ; 0 requête Mongo depuis
callback Dash
**Constraints**: 1 worker Gunicorn (`--workers 1 --threads 4`), cache RAM singleton, stack minimal
(Dash + Plotly + pymongo + requests + python-dotenv + gunicorn), aucun ORM, aucun framework web
supplémentaire
**Scale/Scope**: 8 utilisateurs CAD.42, ~6 projets actifs, ~50–500 dispositifs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Statut | Vérification |
|----------|--------|--------------|
| I. Proportionnalité | ✅ PASS | 8 utilisateurs, 1 worker Gunicorn, ≤ 1 approbateur (CTO/RSSI) |
| II. Auth déléguée | ✅ PASS | before_request + auth-api Microsoft, 403 pré-session, cookie httpOnly SHA-256 |
| III. MongoDB read-only | ✅ PASS | Lecture seule collections métier ; écriture snapshots/alert_history uniquement |
| IV. Cache obligatoire | ✅ PASS | load_all_data 2-temps, MongoClient singleton, 0 appel Mongo depuis callback |
| V. Iso-interface | ✅ PASS | api/mongo_loader.py reproduit exactement les clés de api/loader.py |
| VI. Layout SMSI | ✅ PASS | Header horizontal fixe, 4 onglets, dark cyber #7DC242/#0a0a0a, pas de sidebar |
| VII. Séparation process | ✅ PASS | alerter.py PM2 séparé, dashboard lecture seule sur alert_history |
| VIII. Secrets hors code | ✅ PASS | 5 vars env, python-dotenv, jamais committées ni loggées |
| IX. Stack minimal | ✅ PASS | Dash + Plotly + pymongo + requests + python-dotenv + gunicorn — aucun ajout |

**Gate 1 (pré-Phase 0)** : ✅ PASS — Toutes les contraintes constitutionnelles satisfaites.

**Gate 2 (post-Phase 1 design)** : ✅ PASS — L'architecture module-par-module respecte la
séparation stricte `api/` → `business/` → `ui/` → `callbacks/`. Aucune couche n'importe depuis
une couche non-adjacente. Le mapping rôles est isolé dans `auth/role_check.py`.

## Project Structure

### Documentation (this feature)

```text
specs/001-unifield-smsi-migration/
├── plan.md              # Ce fichier
├── research.md          # Phase 0 — technologies, patterns, décisions architecturales
├── data-model.md        # Phase 1 — entités MongoDB, structures de cache
├── quickstart.md        # Phase 1 — guide de démarrage développeur
├── contracts/
│   ├── auth-routes.md   # Contrats routes /auth/* (Flask/app.server)
│   └── flask-routes.md  # Contrat route /mailgun-webhook
├── progress-log.md      # Journal d'actions pour rapport final
└── tasks.md             # Phase 2 — /speckit.tasks output (pas encore créé)
```

### Source Code (repository root)

```text
api/
├── mongo_client.py          # NOUVEAU — MongoClient singleton lazy/post-fork + pool params
├── mongo_loader.py          # NOUVEAU — load_all_data iso-interface, 2-temps, adaptation champs
├── loader.py                # CONSERVÉ derrière UNIFIELD_SOURCE=rest (fallback dev)
└── client.py                # CONSERVÉ derrière UNIFIELD_SOURCE=rest (fallback dev)

auth/
├── __init__.py              # NOUVEAU
├── role_check.py            # NOUVEAU — mapping rôles auth-api → internes, NoUnifieldRoleError
├── session_store.py         # NOUVEAU — dict RAM sha256(sid), TTL cleanup
├── session_cookie.py        # NOUVEAU — lecture/écriture cookie unifield.sid httpOnly
├── microsoft_flow.py        # NOUVEAU — flow Authorization Code vers auth-api ServiceConsumer
└── routes.py                # NOUVEAU — /auth/login /auth/complete /auth/logout /auth/me

business/
├── trackers.py              # CONSERVÉ SANS MODIFICATION
├── flags.py                 # CONSERVÉ SANS MODIFICATION
├── schedule.py              # CONSERVÉ SANS MODIFICATION
├── segments.py              # CONSERVÉ SANS MODIFICATION
└── alerts.py                # CONSERVÉ SANS MODIFICATION

callbacks/
├── auth.py                  # MODIFIÉ — store-creds depuis session SSO ; save_seuils IDs inchangés
├── sync.py                  # MODIFIÉ — interval-15min, statut dégradé, conn-status MongoDB
├── tabs.py                  # MODIFIÉ — 4 onglets, callback snapshots isolé, active-tab store
├── filters.py               # CONSERVÉ SANS MODIFICATION
├── interactions.py          # CONSERVÉ SANS MODIFICATION
└── modals.py                # CONSERVÉ SANS MODIFICATION

ui/
├── layout.py                # MODIFIÉ — header SMSI, 4 boutons onglets, sans sidebar
├── components.py            # CONSERVÉ SANS MODIFICATION
└── tabs/
    ├── dashboard.py         # NOUVEAU — Onglet 1 : render_urgences + graphe snapshots
    ├── dispositifs.py       # RENOMMÉ depuis capteurs.py (render_capteurs inchangé)
    ├── projets.py           # MODIFIÉ — fusion render_scores intégré dans render_projets
    ├── alertes.py           # NOUVEAU — Onglet 4 : seuils + alert_history + statut alerter
    └── urgences.py          # CONSERVÉ (render_urgences importé depuis dashboard.py)

assets/
└── custom.css               # MODIFIÉ — palette dark cyber Z42 (#7DC242 / #0a0a0a)

app.py                       # MODIFIÉ — requests_pathname_prefix, routes auth, before_request
config.py                    # MODIFIÉ — UNIFIELD_MONGO_URI, UNIFIELD_MONGO_DB, BASE_PATH, APP_ENV
cache.py                     # MODIFIÉ — source mongo_loader, singleton clé fixe, save_snapshot
alerter.py                   # MODIFIÉ — écriture alert_history MongoDB à chaque envoi

tests/
├── test_role_check.py       # NOUVEAU — pytest auth/role_check
└── test_session_store.py    # NOUVEAU — pytest auth/session_store
```

**Structure Decision**: La structure Dash racine existante est conservée (proportionnalité principe I).
Pas de déplacement de l'app dans un sous-dossier. Les seuls ajouts de couches sont le package
`auth/` (nouveau, isolé) et la distinction `api/mongo_client.py` + `api/mongo_loader.py` (remplace
`api/loader.py` + `api/client.py`).

## Phasage et chemin critique

```
Phase 0 — Prérequis externes (Mathieu)
  ├── UNIFIELD_MONGO_URI + accès Atlas (lecture seule collections métier)
  ├── Dump collections MongoDB de référence pour validation iso-interface
  └── ServiceConsumer auth-api enregistré avec slug "unifield"

  ↓ bloquant pour Phase 1 et Phase 2

Phase 1 — MongoDB                  Phase 2 — Auth SSO
api/mongo_client.py                auth/ package (5 modules)
api/mongo_loader.py                before_request dans app.py
cache.py refacto (source + cache   callbacks/auth.py (store-creds
singleton + save_snapshot)         depuis session SSO)
alerter.py → alert_history

  ↓ Phase 1 (snapshots)             ↓ Phase 2 (before_request)

Phase 3 — Refonte Layout           Phase 4 — Réseau / PM2
ui/layout.py header SMSI           config.py BASE_PATH / APP_ENV
4 onglets + callbacks/tabs.py      nginx conf /unifield/ pass-through
interval-15min                     ecosystem.config.js (PM2)
callback snapshots isolé

Phase 5 — Charte Z42 (indépendante dès Phase 0)
assets/custom.css dark cyber palette
```

**Chemin critique** :
- `Phase 0` → `Phase 1` → `Phase 3` (graphe snapshots dépend du loader Mongo)
- `Phase 0` → `Phase 2` → `Phase 4` (nginx/PM2 dépendent du SSO opérationnel)
- `Phase 5` : parallélisable dès la fin de Phase 0

## Validation et critères d'acceptance

| Critère | Méthode |
|---------|---------|
| Iso-interface loader Mongo | Diff structurel `load_all_data()` vs jeu de référence REST — 0 écart de clé ou d'enrichissement `_*` |
| Auth SSO | pytest `test_role_check.py` + `test_session_store.py` ; recette login Microsoft / 403 sans rôle |
| Dégradation MongoDB | Couper Atlas → cache conservé, header rouge, app ne crash pas |
| 4 onglets sans régression | Recette staging : navigation, filtres, clic dispositif, détail projet |
| Graphe snapshots | Attendre 2 cycles de refresh (30 min) → graphe alimenté et sélecteur projet/plage fonctionnel |
| Historique alertes | Déclencher une alerte depuis alerter.py → entrée visible dans Onglet 4 |
| Secrets | `grep -r "UNIFIELD_MONGO_URI\|SECRET\|API_KEY" . --include="*.py"` → 0 résultat hors config.py |
| Webhook HMAC | Envoyer une requête avec signature invalide → 403 immédiat |

## Complexity Tracking

> Aucune violation constitutionnelle — section vide intentionnellement.

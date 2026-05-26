# Data Model: Migration UNIFIELD — Console SMSI CAD.42

**Branch**: `001-unifield-smsi-migration` | **Date**: 2026-05-26

---

## Entités MongoDB (collections existantes — lecture seule)

### `projects`

Collection principale des projets UNIFIELD.

| Champ | Type | Description |
|-------|------|-------------|
| `_id` | ObjectId | Identifiant MongoDB |
| `id` | string | Identifiant métier (clé externe) |
| `name` | string | Nom du projet |
| `code` | string | Code court du projet |
| `type` | string | Type de projet |
| `description` | string | Description longue |
| `startDate` | ISODate | Date de début |
| `endDate` | ISODate | Date de fin prévue |
| `archived` | bool | `true` = archivé |

**Filtre projets actifs** : `archived == False AND endDate > utcnow()`

---

### `trackers`

Dispositifs de tracking (trackers GPS/IoT).

| Champ | Type | Description |
|-------|------|-------------|
| `_id` | ObjectId | Identifiant MongoDB |
| `id` | string | Identifiant métier |
| `project_id` | string | Référence au projet (join Python, pas $lookup) |
| `lastTrack` | object | Dernier envoi de données |
| `lastTrack.ts` | ISODate | Timestamp du dernier envoi |
| `lastTrack.message` | object | Payload du tracker |
| `lastTrack.message.battery_volt` | float | Tension batterie (V) |
| `lastUpdate` | ISODate | Dernière mise à jour de la fiche |

**Enrichissements ajoutés par `mongo_loader.py`** (iso-interface avec `api/loader.py`) :

| Champ enrichi | Type | Calculé depuis |
|---------------|------|----------------|
| `_is_connected` | bool | `lastUpdate` vs schedule actuel |
| `_battery_volt` | float | `lastTrack.message.battery_volt` (adaptation si champ plat) |
| `_project_name` | string | Join Python `project_id` → `projects.name` |

---

### `units`

Unités de déploiement rattachées à un projet.

| Champ | Type | Description |
|-------|------|-------------|
| `_id` | ObjectId | Identifiant MongoDB |
| `project_id` | string | Référence projet |
| `tracker_id` | string | Référence tracker |
| `status` | string | Statut courant |

---

### `events`

Événements terrain (déploiements, interventions, incidents).

| Champ | Type | Description |
|-------|------|-------------|
| `_id` | ObjectId | Identifiant MongoDB |
| `project_id` | string | Référence projet |
| `ts` | ISODate | Horodatage événement |
| `type` | string | Type d'événement |
| `payload` | object | Données métier de l'événement |

---

### `schedule`

Plages horaires de couverture prévues par projet.

| Champ | Type | Description |
|-------|------|-------------|
| `_id` | ObjectId | Identifiant MongoDB |
| `project_id` | string | Référence projet |
| `days` | [string] | Jours de couverture (`["lundi", "mardi", ...]`) |
| `slots` | [object] | Créneaux horaires `{start, end}` |

---

### `scores`

Scores qualité calculés par projet.

| Champ | Type | Description |
|-------|------|-------------|
| `_id` | ObjectId | Identifiant MongoDB |
| `project_id` | string | Référence projet |
| `score` | float | Score qualité global (0–100) |
| `details` | object | Décomposition du score par critère |
| `computed_at` | ISODate | Date de calcul |

---

## Entités MongoDB (collections en écriture)

### `snapshots` *(écrit par le dashboard)*

Enregistrements périodiques de l'état agrégé d'un projet, insérés par `save_snapshot()` à chaque
cycle de refresh réussi.

| Champ | Type | Description |
|-------|------|-------------|
| `_id` | ObjectId | Identifiant MongoDB (auto) |
| `project_id` | string | `"__all__"` pour vue globale, sinon ID projet |
| `ts` | ISODate | Horodatage de l'insertion (utcnow()) |
| `connected` | int | Nb dispositifs connectés au moment du snapshot |
| `disconnected` | int | Nb dispositifs déconnectés |
| `battery_low` | int | Nb dispositifs en alerte batterie |

**Index recommandé** : `{ project_id: 1, ts: -1 }` pour les requêtes par projet + plage temporelle.

**Rétention** : Pas de TTL défini dans cette spec — à configurer par le DBA si nécessaire.

---

### `alert_history` *(écrit exclusivement par alerter.py)*

Historique des envois d'alerte Mailgun. Le dashboard lit en lecture seule.

| Champ | Type | Description |
|-------|------|-------------|
| `_id` | ObjectId | Identifiant MongoDB (auto) |
| `ts` | ISODate | Horodatage d'envoi |
| `subject` | string | Sujet de l'email d'alerte |
| `issues_count` | int | Nombre de problèmes détectés |
| `recipients` | [string] | Liste des destinataires |
| `mailgun_status` | string | `"sent"` / `"delivered"` / `"bounced"` / `"failed"` |

**Index recommandé** : `{ ts: -1 }` pour la pagination des 50 dernières entrées.

---

## Structure du cache serveur (`CacheServeur`)

Dictionnaire Python en RAM, clé fixe unique par process. Accessible par tous les callbacks via
`cache.get_cached_data()`. Signataire conservée : `get_cached_data(email, key)` mais arguments
ignorés en interne.

```python
{
    "projects": [...],           # liste de dicts projets avec enrichissements
    "project_data": {            # dict project_id → detail complet
        "<project_id>": {
            "trackers": [...],
            "units": [...],
            "events": [...],
            "schedule": {...},
            "scores": {...},
        }
    },
    "all_units": [...],          # liste plate de toutes les unités
    "all_trackers": [...],       # liste plate de tous les trackers (enrichis)
    "all_events": [...],         # liste plate de tous les événements
    "qc": {...},                 # métadonnées qualité (compat iso-interface)
    "loaded_at": "2026-05-26T14:30:00Z",  # ISO 8601 UTC
    "_mongo_ok": True,           # statut dernière connexion MongoDB
    "_last_success": "...",      # horodatage dernier refresh réussi
}
```

---

## Session utilisateur (RAM — store `session_store.py`)

```python
# Clé interne : sha256(sid) (valeur du cookie unifield.sid)
{
    "email": "user@cad42.com",
    "role": "app:unifield:read",   # rôle résolu par role_check.py
    "created_at": 1748268600.0,    # timestamp Unix
    "expires_at": 1748354600.0,    # timestamp Unix (TTL)
}
```

---

## Store Dash : `store-seuils`

Store Dash qui persiste les seuils d'alerte. Structure inchangée :

```json
{
    "bt": 3.6,    // seuil batterie (V)
    "ed": 7,      // seuil fin imminente (jours)
    "am": 120,    // seuil inactivité (minutes)
    "pd": null    // paramètre optionnel additionnel
}
```

---

## Store Dash : `active-tab`

```json
"dashboard"   // valeurs possibles : "dashboard" | "dispositifs" | "projets" | "alertes"
```

---

## Store Dash : `conn-status` (statut MongoDB header)

```json
{
    "ok": true,
    "last_success": "2026-05-26T14:30:00Z"
}
```

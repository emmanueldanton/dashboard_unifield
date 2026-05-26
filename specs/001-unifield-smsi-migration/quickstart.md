# Quickstart développeur: Migration UNIFIELD — Console SMSI CAD.42

**Branch**: `001-unifield-smsi-migration` | **Date**: 2026-05-26

---

## Prérequis

- Python 3.13 installé
- Accès à un fichier `.env` local (template ci-dessous)
- (Optionnel) MongoDB Atlas URI de test ou dump local

---

## Variables d'environnement (.env)

```env
# MongoDB Atlas
UNIFIELD_MONGO_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/
UNIFIELD_MONGO_DB=unifield

# Auth SSO (auth-api ServiceConsumer)
AUTH_API_BASE_URL=https://auth-api.cad42.internal
AUTH_API_SERVICE_CONSUMER_SECRET=<secret>

# Mailgun
MAILGUN_API_KEY=<key>
MAILGUN_WEBHOOK_SIGNING_KEY=<signing_key>

# Application
APP_ENV=development
BASE_PATH=/unifield/
PUBLIC_URL=http://localhost:8050

# Dev bypass (JAMAIS en production)
UNIFIELD_DEV_AUTH_BYPASS=true

# Source de données (dev = rest ou mongo)
UNIFIELD_SOURCE=mongo
```

**Important** : Ne jamais commiter ce fichier. Il est listé dans `.gitignore`.

---

## Installation

```bash
pip install -r requirements.txt
```

---

## Démarrage en mode développement (bypass auth)

```bash
# Avec bypass SSO (formulaire email/clé)
UNIFIELD_DEV_AUTH_BYPASS=true APP_ENV=development python app.py
```

L'app est accessible sur `http://localhost:8050/unifield/`.

---

## Démarrage en mode développement (SSO actif)

```bash
# SSO Microsoft actif — nécessite auth-api accessible et slug "unifield" enregistré
APP_ENV=development python app.py
```

---

## Validation iso-interface du loader Mongo

```bash
# Générer le jeu de référence REST (une seule fois)
UNIFIELD_SOURCE=rest python -c "
import json, cache
data = cache.load_fresh()
with open('ref_rest.json', 'w') as f:
    json.dump(data, f, indent=2, default=str)
"

# Comparer avec le loader Mongo
UNIFIELD_SOURCE=mongo python -c "
import json, cache
data = cache.load_fresh()
with open('ref_mongo.json', 'w') as f:
    json.dump(data, f, indent=2, default=str)
"

diff ref_rest.json ref_mongo.json
# Attendu : 0 écart sur les clés et les champs _*
```

---

## Tests unitaires

```bash
pytest tests/test_role_check.py tests/test_session_store.py -v
```

---

## Checklist de recette staging

```
[ ] 1. Login Microsoft → session créée → email visible dans header
[ ] 2. Utilisateur sans rôle app:unifield:* → 403 explicite, aucune session
[ ] 3. Coupure Atlas (désactiver URI temporairement) → cache conservé, header rouge, pas de crash
[ ] 4. Tous les 4 onglets naviguent sans erreur console
[ ] 5. Onglet Dispositifs : filtres connexion + batterie + projet fonctionnels
[ ] 6. Onglet Projets : cartes affichées, filtres, détail avec score
[ ] 7. Graphe évolution (Onglet 1) : après 2 cycles de 15 min → données snapshots visibles
[ ] 8. Onglet Alertes : historique alert_history affiché, seuils modifiables
[ ] 9. Bouton Actualiser → refresh déclenché, date/heure mise à jour
[10] 10. Webhook Mailgun avec signature invalide → 403
[11] 11. `grep -r "UNIFIELD_MONGO_URI\|SECRET\|API_KEY" . --include="*.py"` → 0 résultat hors config.py
```

---

## Structure des logs

Chaque événement loggé suit le format JSON structuré :

```json
{
    "event": "mongo_refresh_ok | mongo_refresh_failed | login | logout | alert_sent | mailgun_webhook",
    "ts": "2026-05-26T14:30:00Z",
    "user": "user@cad42.com",    // si applicable
    "detail": "..."              // jamais un secret
}
```

Fichier de log : `logs/unifield.log` (rotatif, configuré dans PM2 ou gunicorn).

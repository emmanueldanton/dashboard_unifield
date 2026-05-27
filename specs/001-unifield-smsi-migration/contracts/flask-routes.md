# Contract: Routes Flask supplémentaires

**Branch**: `001-unifield-smsi-migration` | **Date**: 2026-05-26
**Module**: `auth/routes.py` (ou directement dans `app.py`)
**Préfixe**: `/unifield/`

---

## POST /unifield/mailgun-webhook

**Rôle** : Réception des événements Mailgun (delivery, bounce, failed) pour mise à jour du statut
dans `alert_history`. Consommé par Mailgun, pas par l'interface utilisateur.

**Authentication** : HMAC-SHA256 obligatoire avant tout traitement.

**Request** :

Headers Mailgun :

| Header | Description |
|--------|-------------|
| Content-Type | `application/x-www-form-urlencoded` ou `application/json` |

Payload Mailgun (champs utilisés) :

| Champ | Type | Description |
|-------|------|-------------|
| `timestamp` | string | Timestamp Unix fourni par Mailgun |
| `token` | string | Token unique de la requête |
| `signature` | string | HMAC-SHA256(timestamp + token, MAILGUN_WEBHOOK_SIGNING_KEY) |
| `event` | string | Type d'événement (`delivered`, `bounced`, `failed`, etc.) |
| `message-id` | string | Message-ID de l'email original |

**Vérification HMAC** :
```
expected = HMAC-SHA256(
    key = MAILGUN_WEBHOOK_SIGNING_KEY (bytes),
    msg = (timestamp + token).encode()
)
si expected != signature → 403 (sans log détaillé)
```

**Response** :
- `200` OK si traitement réussi
- `403` si signature HMAC invalide (sans détail dans le corps de la réponse)
- `400` si payload malformé (champs requis absents)

**Effets** :
- Met à jour `mailgun_status` dans la collection `alert_history` pour le document correspondant
  (matching sur `message-id`)
- Log structuré : `{"event": "mailgun_webhook", "type": "<event>", "ts": "..."}`

**Sécurité** :
- Le secret `MAILGUN_WEBHOOK_SIGNING_KEY` n'est jamais loggé
- Le 403 en cas de signature invalide ne révèle pas la raison du rejet

---

## Route statique et préfixe Dash

**Toutes les routes Dash** sont servies sous `/unifield/` via :
```python
app = dash.Dash(
    __name__,
    server=app_server,
    requests_pathname_prefix="/unifield/",
    routes_pathname_prefix="/unifield/",
)
```

**nginx configuration** (pass-through sans strip) :
```nginx
location /unifield/ {
    proxy_pass http://127.0.0.1:<PORT>/unifield/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    # X-User-Email NOT forwarded (interdit en production)
}
```

**PM2 ecosystem.config.js** :
```javascript
{
  name: "unifield-dashboard",
  script: "gunicorn",
  args: "app:server --workers 1 --threads 4 --bind 0.0.0.0:<PORT>",
  env: { APP_ENV: "production" }
}
```

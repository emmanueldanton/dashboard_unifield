# Contract: Routes d'authentification SSO (/auth/*)

**Branch**: `001-unifield-smsi-migration` | **Date**: 2026-05-26
**Module**: `auth/routes.py` enregistré comme Blueprint Flask sur `app.server`
**Préfixe**: `/unifield/auth/`

---

## GET /unifield/auth/login

**Rôle** : Point d'entrée du flow Microsoft Authorization Code.

**Request** : Aucun paramètre requis. Le middleware `before_request` redirige vers cette route
automatiquement (302) pour les requêtes HTML sans session valide.

**Response** :
- `302` → URL de connexion Microsoft via auth-api (contient `state`, `nonce`, `redirect_uri`)

**Effets** : Génère un `state` aléatoire sauvegardé en session temporaire pour validation CSRF.

---

## GET /unifield/auth/complete

**Rôle** : Callback OAuth2 — reçoit le code d'autorisation Microsoft, échange contre un token,
vérifie le rôle, crée la session.

**Request** :

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `code` | string | ✅ | Code d'autorisation Microsoft |
| `state` | string | ✅ | Valeur CSRF générée par /login |

**Response** :
- `302` → `/unifield/` (succès, session créée, cookie `unifield.sid` posé)
- `403` → Page d'erreur explicite "Accès refusé — aucun rôle UNIFIELD" (utilisateur sans rôle)
- `400` → Erreur si `state` invalide ou `code` manquant

**Effets** :
- Échange `code` contre token via `microsoft_flow.py` → appel auth-api
- Vérifie le rôle via `role_check.py` (lève `NoUnifieldRoleError` si aucun rôle valide)
- Si rôle valide : crée entrée dans `session_store.py`, pose cookie `unifield.sid` httpOnly
- Si rôle invalide : aucune session créée, retourne 403

---

## GET /unifield/auth/logout

**Rôle** : Invalide la session courante.

**Request** : Cookie `unifield.sid` présent.

**Response** :
- `302` → Page de déconnexion auth-api (ou `/unifield/auth/login` si auth-api n'a pas de page dédiée)

**Effets** :
- Supprime l'entrée de session dans `session_store.py`
- Expire le cookie `unifield.sid` (`Max-Age=0`)

---

## GET /unifield/auth/me

**Rôle** : Retourne les métadonnées de la session courante (usage interne/debug).

**Request** : Cookie `unifield.sid` valide requis.

**Response** :
- `200` JSON `{ "email": "...", "role": "...", "expires_at": ... }`
- `401` si pas de session valide

**Sécurité** : Route protégée par `before_request`. Non exposée publiquement en production.

---

## Middleware before_request

**Déclenchement** : Sur toutes les requêtes entrantes de `app.server` (Flask).

**Logique** :
```
si APP_ENV == "production" OU UNIFIELD_DEV_AUTH_BYPASS != "true":
    si request.path commence par /unifield/auth/:
        laisser passer (routes auth elles-mêmes ne sont pas protégées)
    si request.path == /unifield/mailgun-webhook:
        laisser passer (vérification HMAC interne)
    si session_store.get(cookie unifield.sid) est invalide ou absent:
        si Accept: application/json → retourner 401
        sinon → retourner 302 /unifield/auth/login
```

---

## Cookie unifield.sid

| Attribut | Valeur |
|----------|--------|
| Name | `unifield.sid` |
| Value | Identifiant de session opaque (UUID v4) |
| HttpOnly | ✅ |
| SameSite | `Lax` |
| Secure | ✅ (HTTPS uniquement) |
| Path | `/unifield/` |
| Max-Age | 86400 s (24h) |

La valeur du cookie n'est jamais loggée. La clé interne dans `session_store.py` est
`sha256(cookie_value)`.

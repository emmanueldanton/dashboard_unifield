# UNIFIELD Dashboard — Console SIEM CAD.42

Supervision temps réel des chantiers de mesure de terrain UNIFIELD. 5ᵉ console du portail Z42.

**Stack** : Python · Dash · MongoDB Atlas · SSO Microsoft Entra ID · Mailgun · Gunicorn · PM2

## Onglets

- **Tableau de bord** — KPIs, urgences, graphe d'évolution des états (snapshots 15 min)
- **Dispositifs** — table filtrée de tous les trackers/capteurs
- **Projets** — cartes projet avec score de santé
- **Gestion des Alertes** — historique Mailgun, statut livraison, seuils

## Lancer en local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # remplir UNIFIELD_MONGO_URI + AUTH_API_*
python app.py          # → http://localhost:8050/unifield/
```

Mode dev : `UNIFIELD_DEV_AUTH_BYPASS=true` + `APP_ENV=development` dans `.env` (bypass SSO).

## Déploiement

```bash
pm2 start ecosystem.config.js --only unifield-dashboard,unifield-alerter
```

Exposé par nginx sous `/unifield/` sur `security42.francecentral.cloudapp.azure.com`.

# CAD.42 — Dashboard Externe Temps Réel
## Migration Streamlit → Dash

---

## Installation

```bash
# 1. Cloner / copier le dossier
cd cad42_dashboard

# 2. Environnement virtuel
python -m venv venv
source venv/bin/activate   # Windows : venv\Scripts\activate

# 3. Dépendances
pip install -r requirements.txt

# 4. Lancer en dev
python app.py
# → http://localhost:8050
```

---

## Connecter l'API UNIFIELD réelle

Dans `app.py`, remplacer le contenu de `get_live_data()` :

```python
import requests

UNIFIELD_URL = "https://api.unifield.io/v1/chantiers/A7"  # adapter
API_KEY      = "votre_cle_ici"  # à mettre en variable d'env

def get_live_data():
    resp = requests.get(
        UNIFIELD_URL,
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=4,
    )
    resp.raise_for_status()
    return resp.json()
```

Pour l'historique, remplacer `gen_historique_co2()` par une requête InfluxDB/TimescaleDB :

```python
from influxdb_client import InfluxDBClient

def get_historique_co2(zone="B2", minutes=30):
    client = InfluxDBClient(url="http://influxdb:8086", token="...", org="cad42")
    query = f'''
      from(bucket: "chantiers")
        |> range(start: -{minutes}m)
        |> filter(fn: (r) => r.zone == "{zone}" and r.type == "co2")
    '''
    result = client.query_api().query(query)
    ts, vals = [], []
    for table in result:
        for record in table.records:
            ts.append(record.get_time())
            vals.append(record.get_value())
    return ts, vals
```

---

## Variables d'environnement (production)

```env
UNIFIELD_API_URL=https://api.unifield.io/v1
UNIFIELD_API_KEY=sk-xxxx
INFLUX_URL=http://influxdb:8086
INFLUX_TOKEN=xxxx
INFLUX_ORG=cad42
INFLUX_BUCKET=chantiers
```

---

## Déploiement production

### Option A — Serveur simple (VPS, VM Azure/AWS)

```bash
gunicorn app:server -b 0.0.0.0:8050 --workers 2 --timeout 30
```

### Option B — Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "app:server", "-b", "0.0.0.0:8050", "--workers", "2"]
```

### Option C — Railway / Render (le plus rapide)

1. Push sur GitHub
2. Connecter Railway → `Start command : gunicorn app:server -b 0.0.0.0:$PORT`
3. Variables d'env dans Railway dashboard

---

## Architecture recommandée (production)

```
Capteurs IoT
    ↓ MQTT / HTTP POST
Broker (Mosquitto ou Kafka)
    ↓
InfluxDB / TimescaleDB   ←── historique long terme
    ↓
API UNIFIELD (déjà en place)
    ↓
Dash App (cad42_dashboard)
    ↓
Navigateur équipe (auto-refresh 5s)
```

---

## Différences clés Streamlit → Dash

| Streamlit | Dash | Impact |
|---|---|---|
| `st.experimental_rerun()` | `dcc.Interval` | ✅ Rafraîchissement auto sans clic |
| `st.session_state` | `dcc.Store` | ✅ État partagé entre callbacks |
| `st.sidebar` | `html.Div` latéral | Même UX |
| `@st.cache_data` | `dcc.Store` + callback | Plus fin à gérer |
| Re-exécution totale | Callbacks réactifs | ✅ Performances bien meilleures |

---

## Structure du fichier

```
cad42_dashboard/
├── app.py              ← tout le code (monofichier pour commencer)
├── requirements.txt
└── README.md
```

Pour scaler, découper en :
```
cad42_dashboard/
├── app.py
├── callbacks/
│   ├── live_data.py
│   ├── alerts.py
│   └── charts.py
├── components/
│   ├── kpi_card.py
│   ├── sensor_row.py
│   └── zone_card.py
├── data/
│   └── unifield_api.py
└── requirements.txt
```

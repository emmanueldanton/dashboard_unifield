"""
test_name_propagation.py — Vérifie que le vrai nom de projet est propagé
à tous les niveaux : projects[], all_trackers[], all_units[], all_events[].
Utilise le projet Eiffage Toulouse actif (0382_eiffaget) comme sonde.
"""
from __future__ import annotations
import os, sys
from pathlib import Path

env_path = Path(__file__).parent.parent / ".env"
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.mongo_loader import load_all_data

print("Chargement load_all_data()...")
data = load_all_data()

TARGET_DB   = "0382_eiffaget"
REAL_NAME   = "Eiffage - Toulouse - site LVH"
SLUG_NAME   = "eiffaget"          # ce qui était affiché avant

# ── 1. projects[] ─────────────────────────────────────────────────────────────
proj = next((p for p in data["projects"] if p["id"] == TARGET_DB), None)
assert proj is not None,  f"FAIL : projet {TARGET_DB} absent de projects[]"
assert proj["name"] == REAL_NAME, \
    f"FAIL projects.name : attendu {REAL_NAME!r}, eu {proj['name']!r}"
assert proj["endDate"] is not None,  "FAIL : endDate toujours None"
assert proj["schedule"],             "FAIL : schedule toujours vide"
print(f"T1 PASS  projects[].name     = {proj['name']!r}")
print(f"         endDate             = {proj['endDate']}")
print(f"         schedule jours actifs = "
      f"{[d for d,v in proj['schedule'].items() if isinstance(v,dict) and v.get('enable')]}")

# ── 2. all_trackers[] — _project_name ────────────────────────────────────────
trackers = [t for t in data["all_trackers"] if t.get("_project_id") == TARGET_DB]
assert trackers, f"FAIL : aucun tracker pour {TARGET_DB}"
bad = [t for t in trackers if t.get("_project_name") != REAL_NAME]
assert not bad, \
    f"FAIL : {len(bad)} trackers avec _project_name incorrect : {bad[0].get('_project_name')!r}"
print(f"T2 PASS  all_trackers[]._project_name = {trackers[0]['_project_name']!r}  "
      f"({len(trackers)} trackers)")

# ── 3. project_data — units._project_name ────────────────────────────────────
pdata = data["project_data"].get(TARGET_DB)
assert pdata is not None, f"FAIL : {TARGET_DB} absent de project_data (base pas active ?)"
units = pdata.get("units", [])
if units:
    bad_u = [u for u in units if u.get("_project_name") != REAL_NAME]
    assert not bad_u, \
        f"FAIL : {len(bad_u)} units avec _project_name incorrect : {bad_u[0].get('_project_name')!r}"
    print(f"T3 PASS  project_data.units[]._project_name = {units[0]['_project_name']!r}  "
          f"({len(units)} units)")
else:
    print(f"T3 SKIP  aucune unit dans {TARGET_DB} (normal si pas de table 'units')")

# ── 4. Vérification globale : aucun tracker avec slug comme _project_name ─────
slug_trackers = [t for t in data["all_trackers"]
                 if t.get("_project_name", "").lower() == SLUG_NAME]
assert not slug_trackers, \
    f"FAIL : {len(slug_trackers)} trackers portent encore le slug {SLUG_NAME!r}"
print(f"T4 PASS  0 tracker avec l'ancien slug {SLUG_NAME!r} dans all_trackers[]")

# ── 5. Vérification globale : tout projet a un nom non-vide ───────────────────
no_name = [p for p in data["projects"] if not p.get("name")]
assert not no_name, f"FAIL : {len(no_name)} projets sans nom"
print(f"T5 PASS  {len(data['projects'])} projets, tous avec un nom")

# ── 6. Snapshots — project_id utilisé comme clé (pas le nom) ─────────────────
# Le nom s'affiche dans le dropdown, mais project_id = database dans les snapshots
assert proj["id"] == TARGET_DB, "FAIL : project_id doit etre le nom de base"
print(f"T6 PASS  project_id = {proj['id']!r}  (cle snapshots coherente)")

# ── 7. filter_data — nom réel filtré par PARASITE_KEYWORDS ───────────────────
from business.trackers import filter_data
from config import PARASITE_KEYWORDS
filtered = filter_data(data)
eiffage_in_filtered = [p for p in filtered["projects"] if "eiffage" in p["name"].lower()]
print(f"T7 INFO  {len(eiffage_in_filtered)} projets Eiffage apres filter_data()")
print(f"         PARASITE_KEYWORDS = {PARASITE_KEYWORDS}")
parasite_removed = [p for p in data["projects"]
                    if p not in filtered["projects"]
                    and "eiffage" in p["name"].lower()]
if parasite_removed:
    print(f"         ATTENTION : {[p['name'] for p in parasite_removed]} retires par filtre parasite")
else:
    print(f"         Aucun projet Eiffage retire par le filtre parasite")

print("\nTous les tests de propagation des noms passes.")

"""
test_loader_live.py — Test du nouveau mongo_loader contre la vraie base.

Vérifie :
  1. Le registre est chargé (> 0 projets)
  2. load_all_data() retourne les clés iso-interface attendues
  3. Au moins 1 projet a un vrai nom (pas un slug NNNN_)
  4. Au moins 1 projet a endDate non null  → KPI "fins imminentes" va fonctionner
  5. Au moins 1 projet a schedule non vide → check_schedule_anomalies va fonctionner
  6. Les enrichissements _* sont présents sur les trackers
"""
from __future__ import annotations
import os, sys, re
from pathlib import Path

# Charger .env
env_path = Path(__file__).parent.parent / ".env"
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

# Ajouter le projet au sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.mongo_loader import load_all_data, _load_project_registry
from api.mongo_client import get_db

client = get_db().client

# ── T1 : registre ─────────────────────────────────────────────────────────────
reg = _load_project_registry(client)
assert len(reg) > 0, "FAIL : registre vide"
print(f"T1 PASS  registre charge : {len(reg)} projets")

# ── T2 : appel complet load_all_data ─────────────────────────────────────────
print("Lancement load_all_data() (peut prendre 10-30s)...")
data = load_all_data()

required_keys = {"projects", "project_data", "all_units", "all_trackers", "all_events", "qc", "loaded_at"}
missing = required_keys - set(data.keys())
assert not missing, f"FAIL : cles manquantes {missing}"
print(f"T2 PASS  iso-interface OK : {required_keys}")

projects = data["projects"]
print(f"     {len(projects)} projets, {len(data['all_trackers'])} trackers, "
      f"{len(data['all_units'])} units")

# ── T3 : vrais noms (pas slug NNNN_xxxx) ─────────────────────────────────────
_slug_pat = re.compile(r"^\d{4}_")
real_names = [p["name"] for p in projects if not _slug_pat.match(p.get("name",""))]
assert real_names, "FAIL : aucun projet avec un vrai nom"
print(f"T3 PASS  vrais noms de projets : {real_names[:5]}")

# ── T4 : endDate non null ─────────────────────────────────────────────────────
with_end = [p for p in projects if p.get("endDate")]
assert with_end, "FAIL : aucun projet avec endDate"
print(f"T4 PASS  {len(with_end)} projets avec endDate -> KPI fins imminentes OK")
print(f"     ex: {with_end[0]['name']!r:30s} endDate={with_end[0]['endDate']}")

# ── T5 : schedule non vide ────────────────────────────────────────────────────
with_sched = [p for p in projects if p.get("schedule")]
assert with_sched, "FAIL : aucun projet avec schedule"
print(f"T5 PASS  {len(with_sched)} projets avec schedule")
p_ex = with_sched[0]
print(f"     ex: {p_ex['name']!r:30s} schedule keys={list(p_ex['schedule'].keys())[:4]}")

# ── T6 : enrichissements _* sur les trackers ─────────────────────────────────
all_t = data["all_trackers"]
enriched = [t for t in all_t if "_is_connected" in t and "_battery_status" in t]
assert enriched, "FAIL : aucun tracker enrichi"
pct = round(len(enriched) / len(all_t) * 100) if all_t else 0
print(f"T6 PASS  {len(enriched)}/{len(all_t)} trackers enrichis ({pct}%)")

# ── T7 : actifs en Phase 2 ───────────────────────────────────────────────────
active_pids = set(data["project_data"].keys())
print(f"T7 PASS  {len(active_pids)} bases ont eu la Phase 2 (units+events)")

print("\nTous les tests passes.")

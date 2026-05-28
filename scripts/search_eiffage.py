"""
search_eiffage.py — Cherche les projets Eiffage dans le registre + charge leurs trackers live.
"""
from __future__ import annotations
import os, sys
from pathlib import Path
from datetime import datetime, timezone

env_path = Path(__file__).parent.parent / ".env"
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.mongo_loader import _load_project_registry, _phase1_load_trackers
from api.mongo_client import get_db

client = get_db().client
reg    = _load_project_registry(client)
now    = datetime.now(timezone.utc)

hits = {db: doc for db, doc in reg.items()
        if "eiffage" in doc.get("name", "").lower()}

print(f"{len(hits)} projet(s) Eiffage trouves dans le registre:\n")
print("=" * 70)

for dbname in sorted(hits, key=lambda x: hits[x].get("name", "")):
    doc = hits[dbname]
    print(f"\n[{dbname}]")
    print(f"  Nom        : {doc.get('name')}")
    print(f"  Type       : {doc.get('type')}")
    print(f"  Archivé    : {doc.get('archived')}")
    print(f"  Début      : {doc.get('startDate')}")
    print(f"  Fin        : {doc.get('endDate')}")

    sched = doc.get("schedule") or {}
    active_days = [d for d, v in sched.items()
                   if isinstance(v, dict) and v.get("enable")]
    print(f"  Schedule   : {active_days if active_days else 'vide / desactive'}")

    # Charger les trackers live pour ce projet
    result = _phase1_load_trackers(client, dbname, now, project_doc=doc)
    if result is None:
        print(f"  Trackers   : base vide ou inaccessible")
        continue

    project_meta, tracker_map, is_active = result
    trackers = list(tracker_map.values())
    connected    = sum(1 for t in trackers if t.get("_is_connected"))
    bat_low      = sum(1 for t in trackers if t.get("_battery_status") == "faible")
    bat_unknown  = sum(1 for t in trackers if t.get("_battery_status") == "inconnu")

    print(f"  Trackers   : {len(trackers)} total | {connected} connectes | "
          f"{len(trackers)-connected} deconnectes")
    print(f"  Batterie   : {bat_low} faible | {bat_unknown} inconnue")
    print(f"  Actif (30s): {'OUI' if is_active else 'non'}")

    # Afficher les 3 premiers trackers
    for t in trackers[:3]:
        lu = t.get("lastUpdate", "?")
        bv = t.get("_battery_volt", -1)
        print(f"    - {t.get('name','?'):20s}  conn={t.get('_is_connected')}  "
              f"batt={bv:.2f}V  lastUpdate={str(lu)[:19]}")
    if len(trackers) > 3:
        print(f"    ... et {len(trackers)-3} autres")

print("\n" + "=" * 70)

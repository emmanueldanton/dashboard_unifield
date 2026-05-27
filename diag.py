"""Diagnostic 2-phases — valide le chargement mongo_loader.py."""
import time
from api.mongo_loader import load_all_data, ACTIVE_TRACKER_SECONDS

t0 = time.time()
data = load_all_data()
elapsed = time.time() - t0

projects  = data["projects"]
active    = [p for p in projects if p.get("active")]
inactive  = [p for p in projects if not p.get("active")]

print(f"Temps de chargement  : {elapsed:.1f}s")
print(f"Bases avec trackers  : {len(projects)}")
print(f"  Actives  (lastUpdate < {ACTIVE_TRACKER_SECONDS}s) : {len(active)}")
print(f"  Inactives                     : {len(inactive)}")
print(f"Trackers total       : {len(data['all_trackers'])}")
print(f"Units total          : {len(data['all_units'])}")

if active:
    sample_pid = active[0]["id"]
    pdata = data["project_data"].get(sample_pid)
    if pdata:
        print(f"\n=== Exemple actif : {sample_pid} ===")
        print(f"Trackers : {len(pdata['trackers'])} | Units : {len(pdata['units'])}")
        for t in pdata["trackers"][:3]:
            print(f"\n  [{t.get('name')}]")
            print(f"    unit           : {t.get('_unit_name')}")
            print(f"    connecté       : {t.get('_is_connected')}")
            print(f"    lastUpdate     : {t.get('lastUpdate')}")
            print(f"    last_seen_s    : {t.get('_last_seen_seconds')}s")
            print(f"    batterie       : {t.get('_battery_status')} ({t.get('_battery_volt')}V)")
            lt = t.get("lastTrack") or {}
            print(f"    GPS            : lat={lt.get('lat')} lon={lt.get('lon')}")
else:
    print(f"\nAucun projet actif (critère : lastUpdate < {ACTIVE_TRACKER_SECONDS}s)")
    print("Échantillon de projets inactifs :")
    for p in inactive[:5]:
        n = sum(1 for t in data["all_trackers"] if t.get("_project_id") == p["id"])
        print(f"  {p['id']} : {n} trackers")

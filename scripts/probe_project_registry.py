"""
probe_project_registry.py — Comprendre la structure complète de cad42Users.projects
et le mapping project.database → base per-projet.
"""
from __future__ import annotations
import os, re
from pathlib import Path
from collections import Counter

env_path = Path(__file__).parent.parent / ".env"
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

from pymongo import MongoClient
client = MongoClient(os.environ["UNIFIELD_MONGO_URI"], serverSelectionTimeoutMS=10_000)
client.admin.command("ping")

# ── 1. Analyser cad42Users.projects ──────────────────────────────────────────
cad42 = client["cad42Users"]
projects = list(cad42["projects"].find(
    {}, {"name": 1, "database": 1, "startDate": 1, "endDate": 1,
         "archived": 1, "type": 1, "offlineDelay": 1}
))

print(f"cad42Users.projects : {len(projects)} docs")

# Préfixes de database
prefixes = Counter()
for p in projects:
    db = p.get("database", "")
    if db:
        prefix = db.split("_")[0] if "_" in db else db[:8]
        prefixes[prefix] += 1

print(f"\nPrefixes des database fields ({len(prefixes)} types):")
for k, v in sorted(prefixes.items(), key=lambda x: -x[1])[:20]:
    print(f"  '{k}' -> {v} projets")

# Montrer 5 projets non archivés avec database
print("\n5 projets non archives:")
actifs = [p for p in projects if not p.get("archived")]
for p in actifs[:5]:
    print(f"  name={p.get('name')!r:30s} database={p.get('database')!r:25s} end={p.get('endDate')}")

# ── 2. Vérifier que les databases existent dans le cluster ───────────────────
all_dbs_set = set(client.list_database_names())
dbs_referenced = {p.get("database", "") for p in projects if p.get("database")}
dbs_existing   = dbs_referenced & all_dbs_set
dbs_missing    = dbs_referenced - all_dbs_set

print(f"\nDatabases référencées dans les projets : {len(dbs_referenced)}")
print(f"  Existantes dans le cluster           : {len(dbs_existing)}")
print(f"  Absentes du cluster                  : {len(dbs_missing)}")
if dbs_missing:
    print(f"  Exemples manquants : {list(dbs_missing)[:5]}")

# ── 3. Vérifier le trackers dans une des bases référencées ───────────────────
_NNNN = re.compile(r"^\d+_")
dbs_nnnn   = {db for db in dbs_existing if _NNNN.match(db)}
dbs_cad42  = {db for db in dbs_existing if db.startswith("cad42")}
dbs_other  = dbs_existing - dbs_nnnn - dbs_cad42

print(f"\nTypes de bases existantes:")
print(f"  NNNN_*  : {len(dbs_nnnn)}")
print(f"  cad42_* : {len(dbs_cad42)}")
print(f"  autres  : {len(dbs_other)} {list(dbs_other)[:5]}")

# 4 projets non archivés qui référencent une base cad42_*
sample_cad42 = [p for p in actifs if (p.get("database") or "").startswith("cad42")][:3]
for p in sample_cad42:
    db_name = p["database"]
    if db_name not in all_dbs_set:
        continue
    db = client[db_name]
    n_trackers = db["trackers"].count_documents({}) if "trackers" in db.list_collection_names() else 0
    t_sample = db["trackers"].find_one({}, {"name":1,"lastUpdate":1}) if n_trackers else None
    print(f"\n  [{db_name}] '{p.get('name')}' -> {n_trackers} trackers")
    if t_sample:
        print(f"    tracker sample: name={t_sample.get('name')}, lastUpdate={t_sample.get('lastUpdate')}")

# ── 5. Schedule sample complet ────────────────────────────────────────────────
sample_with_sched = next((p for p in actifs if p.get("_id")), None)
full = cad42["projects"].find_one(
    {"archived": False, "schedule": {"$exists": True}},
    {"name": 1, "schedule": 1, "offlineDelay": 1, "type": 1,
     "startDate": 1, "endDate": 1, "database": 1, "timezone": 1}
)
if full:
    print(f"\nSchedule sample (projet '{full.get('name')}'):")
    print(f"  offlineDelay = {full.get('offlineDelay')}")
    print(f"  type         = {full.get('type')}")
    print(f"  timezone     = {full.get('timezone') or full.get('utc')}")
    sched = full.get("schedule", {})
    for day, cfg in list(sched.items())[:3]:
        print(f"  schedule[{day}] = {cfg}")

print("\nDone.")

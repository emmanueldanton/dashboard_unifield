"""
probe_where_is_project_meta.py — Cherche où sont stockées les métadonnées projet
(name, startDate, endDate, schedule, offlineDelay).

Stratégie :
  1. Inspecter la base centrale UNIFIELD_MONGO_DB (unifield)
  2. Inspecter trackerconfigs (présent dans beaucoup de bases)
  3. Inspecter un sample de trackers pour voir s'ils portent des champs projet
  4. Inspecter globals / tasks / configs si présents
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

MONGO_URI = os.environ.get("UNIFIELD_MONGO_URI", "")
MONGO_DB  = os.environ.get("UNIFIELD_MONGO_DB", "unifield")

from pymongo import MongoClient
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10_000)
client.admin.command("ping")
print("Connexion OK\n")

# ── 1. Base centrale ──────────────────────────────────────────────────────────
print("=" * 60)
print(f"[BASE CENTRALE : {MONGO_DB}]")
central_db = client[MONGO_DB]
central_cols = sorted(central_db.list_collection_names())
print(f"  Collections : {central_cols}")

for cname in central_cols:
    doc = central_db[cname].find_one()
    if doc:
        print(f"  {cname}: {list(doc.keys())[:10]}")

# ── 2. Première base projet active avec trackers ──────────────────────────────
import re
_DB_PATTERN = re.compile(r"^\d+_")
all_dbs = [db for db in client.list_database_names() if _DB_PATTERN.match(db)]

# Prendre 10 bases avec des trackers
sample_dbs = []
for dbname in sorted(all_dbs):
    db = client[dbname]
    if db["trackers"].count_documents({}) > 0:
        sample_dbs.append(dbname)
    if len(sample_dbs) >= 10:
        break

print(f"\n{len(sample_dbs)} bases avec trackers : {sample_dbs}")

for dbname in sample_dbs[:3]:  # inspecter les 3 premières
    db   = client[dbname]
    cols = set(db.list_collection_names())
    print(f"\n[{dbname}]")

    # trackerconfigs
    if "trackerconfigs" in cols:
        doc = db["trackerconfigs"].find_one()
        if doc:
            print(f"  trackerconfigs (1er): {list(doc.keys())}")
            for k in ("name", "startDate", "endDate", "schedule",
                      "offlineDelay", "project", "config"):
                if k in doc:
                    print(f"    {k} = {repr(doc[k])[:80]}")

    # globals
    if "globals" in cols:
        doc = db["globals"].find_one()
        if doc:
            print(f"  globals (1er): {list(doc.keys())}")
            for k in ("name", "startDate", "endDate", "schedule",
                      "offlineDelay", "project"):
                if k in doc:
                    print(f"    {k} = {repr(doc[k])[:80]}")

    # tracker sample — chercher champs projet
    tracker = db["trackers"].find_one()
    if tracker:
        print(f"  tracker sample: {list(tracker.keys())}")
        for k in ("name", "startDate", "endDate", "schedule", "offlineDelay",
                  "project", "config", "description", "type"):
            if k in tracker:
                print(f"    {k} = {repr(tracker[k])[:80]}")

        # Suivre la ref config si présente
        config_ref = tracker.get("config") or tracker.get("project")
        if config_ref and "trackerconfigs" in cols:
            cfg_doc = db["trackerconfigs"].find_one({"_id": config_ref})
            if cfg_doc:
                print(f"  trackerconfig résolu: {list(cfg_doc.keys())}")
                for k in ("name", "startDate", "endDate", "schedule",
                          "offlineDelay", "type", "city"):
                    if k in cfg_doc:
                        print(f"    {k} = {repr(cfg_doc[k])[:80]}")

    # tasks (parfois contient la config projet)
    if "tasks" in cols:
        doc = db["tasks"].find_one()
        if doc:
            print(f"  tasks (1er): {list(doc.keys())}")

print("\nDiagnostic termine.")

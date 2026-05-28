"""
probe_all_databases.py — Liste toutes les bases du cluster Atlas
et cherche laquelle contient la collection 'projects' NON VIDE
avec name/startDate/endDate/schedule.
"""
from __future__ import annotations
import os, re
from pathlib import Path

env_path = Path(__file__).parent.parent / ".env"
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

from pymongo import MongoClient
client = MongoClient(os.environ["UNIFIELD_MONGO_URI"], serverSelectionTimeoutMS=10_000)
client.admin.command("ping")

all_dbs = sorted(client.list_database_names())
_PROJ = re.compile(r"^\d+_")
non_project_dbs = [db for db in all_dbs if not _PROJ.match(db)]
print(f"Toutes les bases NON-NNNN_* ({len(non_project_dbs)}) :")
print("  " + str(non_project_dbs))

print()
for dbname in non_project_dbs:
    db   = client[dbname]
    cols = set(db.list_collection_names())
    if not cols:
        continue
    print(f"\n[{dbname}]  cols={sorted(cols)[:15]}")
    if "projects" in cols:
        n   = db["projects"].count_documents({})
        doc = db["projects"].find_one() if n else None
        print(f"  projects: {n} docs")
        if doc:
            print(f"    champs: {list(doc.keys())}")
            for k in ("name","startDate","endDate","schedule","offlineDelay","type","city","archived","database"):
                if k in doc:
                    print(f"      {k} = {repr(doc[k])[:80]}")

# Suivre la ref ObjectId du 1er tracker de 0085_centreaq
print("\n--- Recherche reference projet depuis 0085_centreaq ---")
db85 = client["0085_centreaq"]
t = db85["trackers"].find_one({}, {"project": 1, "name": 1})
if t:
    proj_oid = t.get("project")
    print(f"  tracker '{t.get('name')}' -> project={proj_oid}")
    # Chercher ce doc dans toutes les bases non-projet
    for dbname in non_project_dbs:
        db = client[dbname]
        if "projects" not in db.list_collection_names():
            continue
        found = db["projects"].find_one({"_id": proj_oid})
        if found:
            print(f"  TROUVE dans [{dbname}].projects : {list(found.keys())}")
            for k in ("name","startDate","endDate","schedule","offlineDelay","type","city"):
                if k in found:
                    print(f"    {k} = {repr(found[k])[:120]}")
            break
    else:
        print("  Non trouve dans les bases non-projet. Cherche dans les bases NNNN_*...")
        for dbname in sorted(all_dbs):
            if not _PROJ.match(dbname):
                continue
            db = client[dbname]
            if "projects" not in db.list_collection_names():
                continue
            found = db["projects"].find_one({"_id": proj_oid})
            if found:
                print(f"  TROUVE dans [{dbname}].projects : {list(found.keys())}")
                for k in ("name","startDate","endDate","schedule","offlineDelay","type"):
                    if k in found:
                        print(f"    {k} = {repr(found[k])[:120]}")
                break

print("\nDone.")

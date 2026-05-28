"""
probe_mongo_structure.py — Diagnostic du schéma réel des bases projets MongoDB.

Lit UNIFIELD_MONGO_URI depuis .env, scanne toutes les bases NNNN_*,
et affiche pour chaque base :
  - collections présentes
  - document sample de 'projects' (champs + types)
  - document sample de 'schedule'  (champs + types)

Usage :
    python scripts/probe_mongo_structure.py
"""
from __future__ import annotations
import re, sys, os
from pathlib import Path

# ── charger .env manuellement (sans dotenv installé) ──────────────────────────
env_path = Path(__file__).parent.parent / ".env"
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

MONGO_URI = os.environ.get("UNIFIELD_MONGO_URI", "")
MONGO_DB  = os.environ.get("UNIFIELD_MONGO_DB", "unifield")

if not MONGO_URI:
    sys.exit("UNIFIELD_MONGO_URI non défini dans .env")

try:
    from pymongo import MongoClient
except ImportError:
    sys.exit("pymongo non installé — pip install pymongo")

_DB_PATTERN = re.compile(r"^\d+_")

# ── helpers ────────────────────────────────────────────────────────────────────

def _type_label(v) -> str:
    if v is None:
        return "null"
    t = type(v).__name__
    if t == "datetime":
        return f"datetime({v.isoformat()[:19]})"
    if isinstance(v, list):
        inner = _type_label(v[0]) if v else "empty"
        return f"list[{inner}]"
    if isinstance(v, dict):
        return f"dict({list(v.keys())[:4]})"
    return f"{t}({repr(v)[:30]})"


def _show_doc(label: str, doc: dict | None):
    if not doc:
        print(f"    {label}: VIDE / introuvable")
        return
    print(f"    {label}:")
    for k, v in doc.items():
        if k == "_id":
            continue
        print(f"      {k:25s} → {_type_label(v)}")


# ── connexion ──────────────────────────────────────────────────────────────────
print(f"Connexion à {MONGO_URI[:40]}…")
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10_000)
try:
    client.admin.command("ping")
    print("OK Connexion etablie\n")
except Exception as exc:
    sys.exit(f"FAIL ping MongoDB : {exc}")

all_dbs      = client.list_database_names()
project_dbs  = [db for db in all_dbs if _DB_PATTERN.match(db)]
print(f"{len(project_dbs)} base(s) projet trouvée(s) : {project_dbs}\n")
print("=" * 70)

for dbname in sorted(project_dbs):
    db   = client[dbname]
    cols = set(db.list_collection_names())
    print(f"\n[{dbname}]")
    print(f"  Collections : {sorted(cols)}")

    # ── projects ──────────────────────────────────────────────────────────────
    if "projects" in cols:
        doc = db["projects"].find_one()
        _show_doc("projects (1er doc)", doc)
        # Zoom sur le champ 'schedule' si présent
        if doc and "schedule" in doc:
            sched = doc["schedule"]
            print(f"      schedule type={type(sched).__name__}, val={repr(sched)[:120]}")
    else:
        print("    projects: ABSENTE")

    # ── schedule (collection séparée) ─────────────────────────────────────────
    if "schedule" in cols:
        doc = db["schedule"].find_one()
        _show_doc("schedule (1er doc)", doc)
    else:
        print("    schedule (collection): ABSENTE")

    # ── trackers : compter + sample offlineDelay ─────────────────────────────
    if "trackers" in cols:
        n = db["trackers"].count_documents({})
        sample = db["trackers"].find_one({}, {"offlineDelay": 1, "lastUpdate": 1})
        delay  = (sample or {}).get("offlineDelay", "absent")
        print(f"    trackers: {n} doc(s), offlineDelay sample={delay}")

print("\n" + "=" * 70)
print("Diagnostic terminé.")

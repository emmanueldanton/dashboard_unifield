"""Benchmark load_all_data() à différents niveaux de parallélisme."""
from __future__ import annotations
import os, sys, time
from pathlib import Path

env_path = Path(__file__).parent.parent / ".env"
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent))

import api.mongo_loader as _ml

for workers in [1, 4, 8]:
    _ml._MAX_P1_WORKERS = workers  # type: ignore[attr-defined]
    t0   = time.perf_counter()
    data = _ml.load_all_data()
    elapsed = time.perf_counter() - t0
    print(f"workers={workers:2d} -> {elapsed:.1f}s  "
          f"({len(data['projects'])} projets, {len(data['all_trackers'])} trackers)")

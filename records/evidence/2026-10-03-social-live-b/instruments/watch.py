#!/usr/bin/env python3
"""Print a timestamped line whenever /v1/models (as WHO) or the rigs' status change.

    watch.py <who> <seconds> [interval]
"""
from __future__ import annotations

import json
import sys
import time

from hub import call, redact, ts

who, limit = sys.argv[1], float(sys.argv[2])
step = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
last = None
end = time.monotonic() + limit
while time.monotonic() < end:
    c1, models, _ = call("GET", "/v1/models", who)
    c2, rigs, _ = call("GET", "/api/v1/rigs", who)
    m = [(x.get("id"), {k: v for k, v in x.items() if k not in ("id", "object", "created")}) for x in (models or {}).get("data", [])] if c1 == 200 else c1
    r = [(x["name"], x["status"], x.get("sharing_mode"), [cd.get("vram_free_mb") for cd in x["cards"]]) for x in rigs["rigs"]] if c2 == 200 else c2
    now = (json.dumps(m, sort_keys=True), json.dumps(r))
    if now != last:
        print(ts(), "models:", redact(now[0]), "| rigs:", now[1], flush=True)
        last = now
    time.sleep(step)

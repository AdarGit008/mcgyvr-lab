#!/usr/bin/env python3
"""Item 6 (hitchhike 6a) through the API: head-rig to hitchhike mode, head-owner
offers the 8B on it (width 2), worker-owner turns ride on, the hub matches,
worker-owner reads /api/v1/me/rungs and sends one ride request."""
from __future__ import annotations

import json
import time

from hub import STATE, call, redact, ts

def show(label, r):
    c, b, dt = r
    print(ts(), label, c, redact(json.dumps(b))[:700])
    return c, b

s = json.loads((STATE / "secrets.json").read_text())
head = s["rigs"]["head-rig"]["id"]
show("PATCH /api/v1/rigs/head-rig sharing_mode=hitchhike (head-owner)", call("PATCH", f"/api/v1/rigs/{head}", "head-owner", {"sharing_mode": "hitchhike"}))
show("POST /api/v1/me/hitchhike/offers width=1 (head-owner, must be refused)", call("POST", "/api/v1/me/hitchhike/offers", "head-owner", {"rig": head, "model": "Qwen3-8B-Q4_K_M.gguf", "width": 1}))
_, offer = show("POST /api/v1/me/hitchhike/offers (head-owner)", call("POST", "/api/v1/me/hitchhike/offers", "head-owner", {"rig": head, "model": "Qwen3-8B-Q4_K_M.gguf", "width": 2, "price_in": "0.5", "price_out": "1"}))
show("GET /api/v1/me/hitchhike/offers (head-owner)", call("GET", "/api/v1/me/hitchhike/offers", "head-owner"))
show("GET /api/v1/me/rungs before ride (worker-owner)", call("GET", "/api/v1/me/rungs", "worker-owner"))
show("PUT /api/v1/me/hitchhike/ride on (worker-owner)", call("PUT", "/api/v1/me/hitchhike/ride", "worker-owner", {"ride": True}))
t0 = time.monotonic()
while True:
    c, b = call("GET", "/api/v1/me/rungs", "worker-owner")[:2]
    if c == 200 and b.get("rungs"):
        break
    if time.monotonic() - t0 > 90:
        break
    time.sleep(1)
print(ts(), f"matched after {time.monotonic() - t0:.1f}s")
show("GET /api/v1/me/rungs (worker-owner)", (c, b, 0))
show("GET /api/v1/me/rungs (requester, ride off)", call("GET", "/api/v1/me/rungs", "requester"))
if b.get("rungs"):
    model = b["rungs"][0]["model"]
    body = {"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 8}
    show(f"POST /v1/chat/completions model={model} (worker-owner, the rider)", call("POST", "/v1/chat/completions", "worker-owner", body))
    show(f"POST /v1/chat/completions model={model} (requester, not matched)", call("POST", "/v1/chat/completions", "requester", body))

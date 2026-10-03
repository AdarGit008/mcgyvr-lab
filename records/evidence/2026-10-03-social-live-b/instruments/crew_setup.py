#!/usr/bin/env python3
"""Item 5 set-up through the API: head-owner makes a crew, worker-owner joins
with the invite code (never printed), head-owner's rig goes to crew mode and is
lent to the crew (PUT /rigs/{id}/crew), head-owner lists the 8B for the crew;
worker-owner tries to list a model (must be refused: members read, owner writes).
Writes the crew id to $STATE/live-b-crew.json."""
from __future__ import annotations

import json

from hub import STATE, call, redact, ts

def show(label, r):
    c, b, dt = r
    print(ts(), label, c, redact(json.dumps(b))[:600])
    return b

s = json.loads((STATE / "secrets.json").read_text())
crew = show("POST /api/v1/crews (head-owner)", call("POST", "/api/v1/crews", "head-owner", {"name": "live-b-crew"}))
cid = crew["id"] if "id" in crew else crew["crew"]["id"]
code = crew.get("invite_code") or crew.get("crew", {}).get("invite_code")
(STATE / "live-b-crew.json").write_text(json.dumps({"id": cid}))
show("POST /api/v1/crews/join (worker-owner, code redacted)", call("POST", "/api/v1/crews/join", "worker-owner", {"code": code}))
show("POST /api/v1/crews/join (requester, wrong code)", call("POST", "/api/v1/crews/join", "requester", {"code": "not-a-code"}))
show(f"GET /api/v1/crews/{cid} (worker-owner)", call("GET", f"/api/v1/crews/{cid}", "worker-owner"))
show(f"GET /api/v1/crews/{cid} (requester, non-member)", call("GET", f"/api/v1/crews/{cid}", "requester"))
head = s["rigs"]["head-rig"]["id"]
show("PATCH /api/v1/rigs/head-rig sharing_mode=crew (head-owner)", call("PATCH", f"/api/v1/rigs/{head}", "head-owner", {"sharing_mode": "crew"}))
show("PUT /api/v1/rigs/head-rig/crew (head-owner)", call("PUT", f"/api/v1/rigs/{head}/crew", "head-owner", {"crew_id": cid}))
show(f"POST /api/v1/crews/{cid}/models 8B (worker-owner, a member)", call("POST", f"/api/v1/crews/{cid}/models", "worker-owner", {"name": "Qwen3-8B-Q4_K_M.gguf"}))
show(f"POST /api/v1/crews/{cid}/models 8B (head-owner, the owner)", call("POST", f"/api/v1/crews/{cid}/models", "head-owner", {"name": "Qwen3-8B-Q4_K_M.gguf"}))
show(f"GET /api/v1/crews/{cid}/models (worker-owner)", call("GET", f"/api/v1/crews/{cid}/models", "worker-owner"))

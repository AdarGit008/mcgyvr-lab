#!/usr/bin/env python3
"""Item 7, forms: as worker-owner, choose worker-rig's crew on /me/rigs (the
web form), then turn riding off and on again on /me/hitchhike."""
from __future__ import annotations

import json

from hub import STATE, key
from web_walk import Browser, text

s = json.loads((STATE / "secrets.json").read_text())
crew = json.loads((STATE / "live-b-crew.json").read_text())["id"]
rig = s["rigs"]["worker-rig"]["id"]
b = Browser()
st, _, hdr = b.go("POST", "/signin", {"csrf": b.csrf("/signin"), "token": key("worker-owner")})
print("signin", st, hdr.get("location"))
for form in ({"crew_id": ""}, {"crew_id": crew}, {"crew_id": "0" * 32}):
    st, body, hdr = b.go("POST", f"/me/rigs/{rig}/crew", {"csrf": b.csrf("/me/rigs"), **form})
    shown = "default" if not form["crew_id"] else ("live-b-crew" if form["crew_id"] == crew else "a crew id that does not exist")
    print(f"POST /me/rigs/<worker-rig>/crew crew_id=<{shown}> ->", st, hdr.get("location", ""), "" if st == 303 else text(body)[-300:].replace("\n", " "))
st, body, _ = b.go("GET", "/me/rigs")
print("now:", [l for l in text(body).splitlines() if "Sharing: " in l or "Lent to" in l])
for ride in ("off", "on"):
    st, _, hdr = b.go("POST", "/me/hitchhike/ride", {"csrf": b.csrf("/me/hitchhike"), "ride": ride})
    print(f"POST /me/hitchhike/ride ride={ride} ->", st, hdr.get("location", ""))

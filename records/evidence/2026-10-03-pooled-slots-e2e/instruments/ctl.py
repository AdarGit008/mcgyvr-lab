#!/usr/bin/env python3
"""Drive the e2e hub through its HTTP API (stdlib only); tools/demo/hubctl.py
with four users and four rigs.

  ctl.py bootstrap            users usr1..usr4 and their rigs (once)
  ctl.py token <rig>          print a rig's join token (into a 0600 file only)
  ctl.py wait-online [s]      wait until every rig is online; print them
  ctl.py rigs                 the rigs as usr1 sees them
  ctl.py sessions             usr1's view of the pool sessions (no secrets)
  ctl.py stop-all             stop every running session usr1 takes part in
  ctl.py plan <ctx>           the hub's plan preview at a context per slot

Users and rigs (every user lends a rig in pool mode, so the access rule lets
each use the others' rigs):
  usr1 owns head-rig (srv1), usr2 owns worker-rig (srv2),
  usr3 owns vps-a and usr4 owns vps-b: agents on the hub's host with no card.
Secrets live in $STATE/secrets.json (0600) and are never printed except by
`token`, whose output goes straight into a 0600 file on the rig.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

STATE = Path(os.environ["STATE"])
HUB = os.environ.get("HUB") or (STATE / "hub.url").read_text().strip()
SECRETS = STATE / "secrets.json"
USERS = ("usr1", "usr2", "usr3", "usr4")
RIGS = {"head-rig": "usr1", "worker-rig": "usr2", "vps-a": "usr3", "vps-b": "usr4"}
MODEL = "Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf"


def call(method: str, path: str, token: str | None = None, body: Any = None) -> Any:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(HUB + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{method} {path}: {exc.code} {exc.read()[:300]!r}") from None
    return json.loads(raw) if raw else None


def secrets() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(SECRETS.read_text())
    return loaded


def bootstrap() -> None:
    if SECRETS.exists():
        print("already bootstrapped")
        return
    out: dict[str, Any] = {"users": {}, "ids": {}, "rigs": {}}
    for handle in USERS:
        made = call("POST", "/api/v1/users", body={"handle": handle})
        out["users"][handle] = made["token"]
        out["ids"][handle] = (made.get("user") or {}).get("id")
    for name, owner in RIGS.items():
        made = call(
            "POST",
            "/api/v1/rigs",
            out["users"][owner],
            {"name": name, "sharing_mode": "pool"},
        )
        out["rigs"][name] = {"id": made["rig"]["id"], "join_token": made["join_token"]}
    old = os.umask(0o077)
    try:
        SECRETS.write_text(json.dumps(out))
    finally:
        os.umask(old)
    print("users:", ", ".join(USERS), "| rigs:", ", ".join(RIGS))


def rigs() -> list[dict[str, Any]]:
    listed: list[dict[str, Any]] = call(
        "GET", "/api/v1/rigs", secrets()["users"]["usr1"]
    )["rigs"]
    return listed


def show() -> None:
    for r in rigs():
        cards = ", ".join(
            f"#{c['index']} {c['name']} {c['vram_free_mb']}/{c['vram_total_mb']} MiB"
            for c in r["cards"]
        )
        print(
            f"{r['name']:<11} owner={r['owner']:<4} {r['sharing_mode']:<6} "
            f"{r['status']:<8} ram {r['ram_free_mb']}/{r['ram_total_mb']} MiB "
            f"agent {r['agent_version']} | {cards or 'no card'}"
        )


def wait_online(limit: float) -> None:
    end = time.monotonic() + limit
    while True:
        status = {r["name"]: r["status"] for r in rigs()}
        if all(status.get(n) == "online" for n in RIGS):
            show()
            return
        if time.monotonic() > end:
            raise SystemExit(f"rigs not online after {limit:.0f} s: {status}")
        time.sleep(2)


def sessions() -> list[dict[str, Any]]:
    got: list[dict[str, Any]] = call(
        "GET", "/api/v1/sessions", secrets()["users"]["usr1"]
    )["sessions"]
    return got


def stop_all() -> None:
    token = secrets()["users"]["usr1"]
    for s in sessions():
        if s.get("state") not in ("stopping", "stopped", "failed"):
            call("POST", f"/api/v1/sessions/{s['id']}/stop", token)
            print("stopped", s["id"], s.get("state"))


def plan(ctx: str) -> None:
    """The pool page's plan preview (signed out: as a pool lender sees it)."""
    q = urllib.parse.urlencode({"model": MODEL, "ctx": ctx})
    with urllib.request.urlopen(f"{HUB}/pool/plan?{q}", timeout=60) as resp:
        page = resp.read().decode()
    text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    print(re.sub(r"\s+", " ", text).strip())


def main(argv: list[str]) -> None:
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "bootstrap":
        bootstrap()
    elif cmd == "token":
        print(secrets()["rigs"][argv[2]]["join_token"])
    elif cmd == "wait-online":
        wait_online(float(argv[2]) if len(argv) > 2 else 120)
    elif cmd == "rigs":
        show()
    elif cmd == "sessions":
        for s in sessions():
            print(json.dumps(s))
    elif cmd == "stop-all":
        stop_all()
    elif cmd == "plan":
        plan(argv[2])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv)

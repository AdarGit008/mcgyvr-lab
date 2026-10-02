#!/usr/bin/env python3
"""Drive the demo hub through its real HTTP API (stdlib only).

  hubctl.py bootstrap            create the three users and the two rigs (once)
  hubctl.py token <name>         print a join token (head-rig|worker-rig)
  hubctl.py wait-online [s]      wait until both rigs are online
  hubctl.py rigs                 the rigs as the requester sees them
  hubctl.py share <rig> <mode>   set a rig's sharing mode as its owner

Secrets live in $STATE/secrets.json (mode 0600) and are never printed except
by `token`, whose output goes straight into a 0600 file on the rig.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

STATE = Path(os.environ["STATE"])
_URL = STATE / "hub.url"  # written by demo-up
HUB = os.environ.get("HUB") or (
    _URL.read_text().strip() if _URL.exists() else "http://127.0.0.1:18765"
)
SECRETS = STATE / "secrets.json"
USERS = ("head-owner", "worker-owner", "requester")
RIGS = {"head-rig": "head-owner", "worker-rig": "worker-owner"}


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
    out: dict[str, Any] = {"users": {}, "rigs": {}}
    for handle in USERS:
        made = call("POST", "/api/v1/users", body={"handle": handle})
        out["users"][handle] = made["token"]
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
    token = secrets()["users"]["requester"]
    listed: list[dict[str, Any]] = call("GET", "/api/v1/rigs", token)["rigs"]
    return listed


def show() -> None:
    for r in rigs():
        cards = ", ".join(
            f"#{c['index']} {c['name']} {c['vram_free_mb']}/{c['vram_total_mb']} MiB"
            for c in r["cards"]
        )
        print(
            f"{r['name']:<11} owner={r['owner']:<13} {r['sharing_mode']:<8} "
            f"{r['status']:<8} ram {r['ram_free_mb']}/{r['ram_total_mb']} MiB "
            f"agent {r['agent_version']} | {cards}"
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


def share(name: str, mode: str) -> None:
    s = secrets()
    owner = s["users"][RIGS[name]]
    rig = call(
        "PATCH", f"/api/v1/rigs/{s['rigs'][name]['id']}", owner, {"sharing_mode": mode}
    )
    print(rig["name"], rig["sharing_mode"])


def main(argv: list[str]) -> None:
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "bootstrap":
        bootstrap()
    elif cmd == "token":
        print(secrets()["rigs"][argv[2]]["join_token"])
    elif cmd == "user-token":
        print(secrets()["users"][argv[2]])
    elif cmd == "wait-online":
        wait_online(float(argv[2]) if len(argv) > 2 else 120)
    elif cmd == "rigs":
        show()
    elif cmd == "share":
        share(argv[2], argv[3])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv)

#!/usr/bin/env python3
"""The binding responder's positive path and the latency probe on the live hub,
with no rig: two of the hub repo's model-less lab agents (tests/natlab/
mini_agent.py, no GPU, no container) run on this machine as throwaway rigs of
the admin user, one bound to the public address and one to the Tailscale
address, so the responder sees two different sources. The admin's plan
preview (/pool/plan) starts a probe between them. Afterwards the agents are
stopped and both throwaway rigs deleted.

Run with the hub checkout's python (the agent needs ``websockets``):

    STATE=... HUB=http://host:port HUB_REPO=... $HUB_REPO/.venv/bin/python agents_probe.py LOGDIR
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HUB = os.environ["HUB"].rstrip("/")
STATE = Path(os.environ["STATE"])
AGENT = Path(os.environ["HUB_REPO"]) / "tests/natlab/mini_agent.py"
ADMIN = json.loads((STATE / "live-a-keys.json").read_text())["admin_signup"]
MODEL = "live-a-lab.gguf"
WRAP = r'''
import importlib.util, sys
spec = importlib.util.spec_from_file_location("mini_agent", sys.argv[1])
m = importlib.util.module_from_spec(spec); sys.modules["mini_agent"] = m
spec.loader.exec_module(m)
_orig = m.bindings
async def logged(port, token, servers):
    seen, rtt = await _orig(port, token, servers)
    m.log("probe", "binding requests to", [(s["host"], s["port"]) for s in servers],
          "-> responder saw us as", seen, "rtt_us", rtt)
    return seen, rtt
m.bindings = logged
sys.argv = sys.argv[1:]
sys.exit(m.main())
'''


def call(method: str, path: str, body: object = None) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(HUB + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {ADMIN}")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw, status = r.read(), r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
    return status, (json.loads(raw) if raw else None)


def text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def main() -> int:
    logs = Path(sys.argv[1])
    logs.mkdir(parents=True, exist_ok=True)
    rigs = {}
    for name in ("live-a-fake-pub", "live-a-fake-ts"):
        status, body = call("POST", "/api/v1/rigs", {"name": name, "sharing_mode": "pool"})
        assert status == 201, (status, body)
        rigs[name] = body  # type: ignore[assignment]
        print(f"rig {name} created: HTTP {status}, id {body['rig']['id'][:8]}…")  # type: ignore[index]
    ws = HUB.replace("http://", "ws://")
    plan = [
        ("live-a-fake-pub", "185.245.183.242", ["--vram-mb", "6000", "--model", f"{MODEL}:16:32"]),
        ("live-a-fake-ts", "100.119.117.59", ["--vram-mb", "22000"]),
    ]
    procs = []
    try:
        for name, ip, extra in plan:
            out = (logs / f"{name}.log").open("wb")
            cmd = [sys.executable, "-c", WRAP, str(AGENT), "--hub", ws, "--token", rigs[name]["join_token"],
                   "--name", name, "--bind-ip", ip, *extra]
            procs.append(subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT))
        time.sleep(4)
        status, body = call("GET", "/api/v1/rigs/mine")
        for r in body["rigs"] if isinstance(body, dict) else []:  # type: ignore[index]
            if r["name"].startswith("live-a-fake"):
                print(f"rig {r['name']}: {r['status']}, {r['sharing_mode']}, cards {[c['vram_total_mb'] for c in r['cards']]}")
        jar = http.cookiejar.CookieJar()
        b = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        page = b.open(HUB + "/signin", timeout=30).read().decode()
        csrf = re.search(r'name="csrf" value="([^"]+)"', page)[1]  # type: ignore[index]
        b.open(HUB + "/signin", data=urllib.parse.urlencode({"csrf": csrf, "token": ADMIN}).encode(), timeout=30).close()
        t0 = time.monotonic()
        with b.open(f"{HUB}/pool/plan?model={urllib.parse.quote(MODEL)}", timeout=60) as r:
            status, html = r.status, r.read().decode()
        print(f"GET /pool/plan?model={MODEL} as admin: HTTP {status} in {time.monotonic() - t0:.2f} s")
        print("plan page text:", text(html)[:900])
        time.sleep(10)  # probe deadline 4 s + its wait
        with b.open(f"{HUB}/pool/plan?model={urllib.parse.quote(MODEL)}", timeout=60) as r:
            print("plan page 10 s later:", text(r.read().decode())[:900])
    finally:
        for p in procs:
            p.terminate()
            p.wait(timeout=10)
        time.sleep(1)
        for name, made in rigs.items():
            status, _ = call("DELETE", f"/api/v1/rigs/{made['rig']['id']}")
            print(f"rig {name} deleted: HTTP {status}")
    for name, _, _ in plan:
        print(f"--- {name}.log")
        print(re.sub(r"[0-9a-f]{32}", "<hex>", (logs / f"{name}.log").read_text()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

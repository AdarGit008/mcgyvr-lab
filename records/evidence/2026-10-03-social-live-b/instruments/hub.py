"""Shared helpers for the live-b instruments (stdlib only).

Tokens come from $STATE/secrets.json (bootstrap users) or $STATE/live-b-keys.json
(web users) and are never printed; redact() masks any token in text we print.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

STATE = Path(os.environ.get("STATE", os.path.expanduser("~/.local/state/mcgyvr-demo")))
HUB = os.environ.get("HUB") or (STATE / "hub.url").read_text().strip()
TOKEN = re.compile(r"mh[a-z]_[0-9a-f]{8,}_[A-Za-z0-9_\-]{8,}")


INVITE = re.compile(r'("invite_code": ?)"[^"]+"')


def redact(text: str) -> str:
    text = INVITE.sub(r'\1"<redacted>"', text)
    return TOKEN.sub(lambda m: m.group(0).split("_")[0] + "_<redacted>", text)


def key(who: str) -> str:
    s = json.loads((STATE / "secrets.json").read_text())
    if who in s["users"]:
        return s["users"][who]
    k = json.loads((STATE / "live-b-keys.json").read_text())
    return k[who]


def call(method: str, path: str, who: str | None = None, body: Any = None,
         headers: dict[str, str] | None = None, timeout: float = 600) -> tuple[int, Any, float]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(HUB + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if who:
        req.add_header("Authorization", f"Bearer {key(who)}")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw, code = r.read(), r.status
    except urllib.error.HTTPError as e:
        raw, code = e.read(), e.code
    dt = time.monotonic() - t0
    try:
        return code, json.loads(raw) if raw else None, dt
    except ValueError:
        return code, raw.decode(errors="replace"), dt


def ts() -> str:
    return time.strftime("%H:%M:%SZ", time.gmtime())

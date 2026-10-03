#!/usr/bin/env python3
"""OpenAI-compatible calls against the live hub, timed (stdlib only).

Keys come from $STATE/live-a-keys.json (web_walk.py) and $STATE/secrets.json
(demo bootstrap); none is printed. Each line: label, HTTP status, seconds,
the error code and message (or the model list).

    STATE=... HUB=http://host:port api_calls.py <label-prefix>
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HUB = os.environ["HUB"].rstrip("/")
STATE = Path(os.environ["STATE"])
KEYS = json.loads((STATE / "live-a-keys.json").read_text())
DEMO = json.loads((STATE / "secrets.json").read_text())["users"]


def call(method: str, path: str, key: str | None, body: object = None, headers: dict[str, str] | None = None) -> tuple[int, float, str, dict[str, str]]:
    data = json.dumps(body).encode() if body is not None and not isinstance(body, bytes) else body
    req = urllib.request.Request(HUB + path, data=data, method=method)  # type: ignore[arg-type]
    req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw, status, hdrs = r.read(), r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        raw, status, hdrs = e.read(), e.code, dict(e.headers)
    return status, time.monotonic() - t0, raw.decode(errors="replace"), hdrs


def show(label: str, result: tuple[int, float, str, dict[str, str]]) -> None:
    status, took, raw, hdrs = result
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = None
    if isinstance(parsed, dict) and isinstance(parsed.get("error"), dict):
        err = parsed["error"]
        what = f"code={err.get('code')} type={err.get('type')} message={err.get('message')!r}"
    elif isinstance(parsed, dict) and "data" in parsed:
        what = f"data={[m.get('id') for m in parsed['data']]}"
    else:
        what = f"body={raw[:200]!r}"
    retry = f" Retry-After={hdrs['Retry-After']}" if "Retry-After" in hdrs else ""
    print(f"{label:<58} HTTP {status}  {took:6.3f} s  {what}{retry}", flush=True)


def chat(model: str, stream: bool = False) -> dict[str, object]:
    return {"model": model, "messages": [{"role": "user", "content": "hi"}], "stream": stream, "max_tokens": 8}


def main() -> int:
    prefix = sys.argv[1] if len(sys.argv) > 1 else ""
    user, requester, owner = KEYS["user_key"], DEMO["requester"], DEMO["head-owner"]
    curated = "Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf"
    show(f"{prefix}GET /v1/models (no key)", call("GET", "/v1/models", None))
    show(f"{prefix}GET /v1/models (live-a-user key)", call("GET", "/v1/models", user))
    show(f"{prefix}GET /v1/models (head-owner key, rig offline)", call("GET", "/v1/models", owner))
    show(f"{prefix}GET /v1/models X-Mcgyvr-Scope: own", call("GET", "/v1/models", user, headers={"X-Mcgyvr-Scope": "own"}))
    show(f"{prefix}GET /v1/models X-Mcgyvr-Scope: bogus", call("GET", "/v1/models", user, headers={"X-Mcgyvr-Scope": "bogus"}))
    show(f"{prefix}POST chat (no key)", call("POST", "/v1/chat/completions", None, chat(curated)))
    show(f"{prefix}POST chat malformed JSON", call("POST", "/v1/chat/completions", user, b"{not json"))
    for who, key in (("live-a-user", user), ("requester", requester), ("head-owner", owner)):
        show(f"{prefix}POST chat {curated[:22]}… ({who})", call("POST", "/v1/chat/completions", key, chat(curated)))
    show(f"{prefix}POST chat stream=true (live-a-user)", call("POST", "/v1/chat/completions", user, chat(curated, True)))
    show(f"{prefix}POST chat unlisted.gguf (live-a-user)", call("POST", "/v1/chat/completions", user, chat("unlisted.gguf")))
    for scope in ("own", "crew"):
        show(f"{prefix}POST chat scope={scope} (live-a-user)", call("POST", "/v1/chat/completions", user, chat(curated), {"X-Mcgyvr-Scope": scope}))
        show(f"{prefix}POST chat scope={scope} (head-owner, rig offline)", call("POST", "/v1/chat/completions", owner, chat(curated), {"X-Mcgyvr-Scope": scope}))
    t0 = time.monotonic()
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(6) as pool:
        futs = [pool.submit(call, "POST", "/v1/chat/completions", k, chat(curated)) for k in (user, requester, owner, user, requester, owner)]
        statuses = [f.result()[0] for f in futs]
    print(f"{prefix}6 concurrent chats (3 users)                            statuses={statuses} all done in {time.monotonic() - t0:.3f} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

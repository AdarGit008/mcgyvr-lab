#!/usr/bin/env python3
"""One chat request through the hub's /v1/chat/completions, timed.

    chat.py <who> <model> [--stream] [--max N] [--scope S] [--prompt TEXT]

Prints status, wall time, time to first byte/token (stream), tokens and tok/s,
and the first 160 chars of the answer (or the error body). For streams every
event's arrival is logged relative to the start with --trace.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request

from hub import HUB, key, redact, ts

p = argparse.ArgumentParser()
p.add_argument("who"); p.add_argument("model")
p.add_argument("--stream", action="store_true"); p.add_argument("--trace", action="store_true")
p.add_argument("--max", type=int, default=128); p.add_argument("--scope")
p.add_argument("--prompt", default="Write a Python function that checks whether a number is prime. Code only.")
a = p.parse_args()
body = {"model": a.model, "messages": [{"role": "user", "content": a.prompt}],
        "max_tokens": a.max, "stream": a.stream, "temperature": 0}
if a.stream:
    body["stream_options"] = {"include_usage": True}
req = urllib.request.Request(HUB + "/v1/chat/completions", data=json.dumps(body).encode(), method="POST")
req.add_header("Content-Type", "application/json")
req.add_header("Authorization", f"Bearer {key(a.who)}")
if a.scope:
    req.add_header("X-Mcgyvr-Scope", a.scope)
t0 = time.monotonic()
print(ts(), f"start who={a.who} model={a.model} stream={a.stream} max={a.max} scope={a.scope}", flush=True)
try:
    r = urllib.request.urlopen(req, timeout=900)
except urllib.error.HTTPError as e:
    print(ts(), f"HTTP {e.code} after {time.monotonic()-t0:.2f}s retry-after={e.headers.get('Retry-After')} body={redact(e.read().decode(errors='replace'))[:400]}")
    raise SystemExit(0)
except Exception as e:  # connection reset etc.
    print(ts(), f"EXC after {time.monotonic()-t0:.2f}s {type(e).__name__}: {e}")
    raise SystemExit(0)
hdr = time.monotonic() - t0
if not a.stream:
    d = json.loads(r.read())
    wall = time.monotonic() - t0
    u = d.get("usage", {})
    msg = d["choices"][0]["message"]
    text = (msg.get("content") or "") or (msg.get("reasoning_content") or "")
    ct = u.get("completion_tokens", 0)
    print(ts(), f"HTTP {r.status} wall={wall:.2f}s prompt_tok={u.get('prompt_tokens')} completion_tok={ct} "
          f"tok/s(wall)={ct/wall:.1f} timings={json.dumps(d.get('timings', {}))[:300]}")
    print("answer:", json.dumps(text[:160]))
    raise SystemExit(0)
first = None; n = 0; usage = None; text = ""; last_line = ""; done = False; err = None
for raw in r:
    line = raw.decode(errors="replace").strip()
    if not line:
        continue
    now = time.monotonic() - t0
    last_line = line
    if a.trace:
        print(f"  +{now:7.2f}s {redact(line)[:160]}")
    if line == "data: [DONE]":
        done = True; continue
    if not line.startswith("data: "):
        continue
    ev = json.loads(line[6:])
    if "error" in ev:
        err = ev["error"]; continue
    if ev.get("usage"):
        usage = ev["usage"]
    for ch in ev.get("choices", []):
        delta = ch.get("delta", {})
        piece = (delta.get("content") or "") + (delta.get("reasoning_content") or "")
        if piece:
            n += 1; text += piece
            if first is None:
                first = now
wall = time.monotonic() - t0
gen = wall - (first or wall)
ct = (usage or {}).get("completion_tokens", n)
print(ts(), f"HTTP {r.status} headers={hdr:.2f}s first_token={first if first is None else round(first, 2)}s wall={wall:.2f}s "
      f"chunks={n} completion_tok={ct} decode tok/s={(ct-1)/gen if gen > 0 and ct > 1 else 0:.1f} done={done} error={json.dumps(err)}")
print("answer:", json.dumps(text[:160]), "| last line:", redact(last_line)[:200])

#!/usr/bin/env python3
"""One chat request through the hub's OpenAI API, timed.

  chat.py stream|plain <prompt> [max_tokens]

Retries a 503 model_loading after its Retry-After (that wait is part of a
cold start's time to first token). Prints one JSON line: status, error code,
time to first token, decode tokens/s (from the engine's own timings when the
stream carries them, else chunks over wall time), the answer.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

HUB = os.environ.get("HUB", "http://127.0.0.1:18765")
TOKEN = os.environ["REQ_TOKEN"]
MODEL = os.environ.get("MODEL", "Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf")


def request(body: dict[str, Any]) -> urllib.request.Request:
    req = urllib.request.Request(
        HUB + "/v1/chat/completions", data=json.dumps(body).encode(), method="POST"
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    return req


def main() -> None:
    mode, prompt = sys.argv[1], sys.argv[2]
    max_tokens = int(sys.argv[3]) if len(sys.argv) > 3 else 128
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "seed": 42,
        "stream": mode == "stream",
    }
    t0 = time.monotonic()
    waits = 0
    out: dict[str, Any] = {"mode": mode}
    while True:
        try:
            resp = urllib.request.urlopen(request(body), timeout=900)
            break
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            try:
                err = json.loads(payload)["error"]
            except Exception:
                err = {"code": None, "message": payload[:200].decode(errors="replace")}
            if exc.code == 503 and err.get("code") == "model_loading" and waits < 200:
                waits += 1
                time.sleep(float(exc.headers.get("Retry-After") or 5))
                continue
            out.update(
                status=exc.code, code=err.get("code"), message=err.get("message")
            )
            out["elapsed_s"] = round(time.monotonic() - t0, 2)
            print(json.dumps(out))
            return
    out["status"] = resp.status
    out["loading_retries"] = waits
    if mode == "plain":
        data = json.loads(resp.read())
        t1 = time.monotonic()
        out["elapsed_s"] = round(t1 - t0, 2)
        out["answer"] = data["choices"][0]["message"]["content"]
        out["usage"] = data.get("usage")
        out["timings"] = data.get("timings")
        print(json.dumps(out))
        return
    first = last = None
    chunks = 0
    text = []
    timings = None
    error = None
    for raw in resp:
        line = raw.decode().strip()
        if not line.startswith("data:"):
            continue
        item = line[5:].strip()
        if item == "[DONE]":
            break
        ev = json.loads(item)
        if "error" in ev:
            error = ev["error"]
            break
        timings = ev.get("timings") or timings
        for ch in ev.get("choices", []):
            piece = (ch.get("delta") or {}).get("content")
            if piece:
                now = time.monotonic()
                first = first or now
                last = now
                chunks += 1
                text.append(piece)
    end = time.monotonic()
    out["ttft_s"] = round(first - t0, 2) if first else None
    out["elapsed_s"] = round(end - t0, 2)
    out["chunks"] = chunks
    if first and last and chunks > 1:
        out["chunks_per_s"] = round((chunks - 1) / (last - first), 2)
    if timings:
        out["engine"] = {
            k: timings.get(k)
            for k in (
                "prompt_n",
                "prompt_per_second",
                "predicted_n",
                "predicted_per_second",
            )
        }
    if error:
        out["stream_error"] = error
    out["answer"] = "".join(text)
    print(json.dumps(out))


if __name__ == "__main__":
    main()

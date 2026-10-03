#!/usr/bin/env python3
"""Send one cell of concurrent streamed chat requests through the hub, timed.

  load.py CELL RUN LABEL [k=v ...] > rows.jsonl

CELL is one of:
  warm        usr1 sends workload draw 0 (retrying 503 model_loading), discarded
  c4          workload draws 4..7, one request each from usr1, usr2, usr3, usr4
  c8          workload draws 4..11, two each: usr1 usr2 usr3 usr4 usr1 usr2 usr3 usr4
  burst       users in `users=` (default usr1,usr2,usr3) each send `per=` (2)
              short requests back to back, user by user (A A B B C C ...)
  long        one request from `user=` with `want=` tokens of workload draw 3
  hangup      one request from `user=` whose client closes after `after=` s

The workload is the lab's (tools/runs/workload.py), drawn in UID order as
step 1's driver drew it, so draw i is step 1's draw i: system prompt split off,
temperature 0, max_tokens = the draw's cap, stream with usage. Requests are
sent in index order, `gap=` seconds apart (default 0.02), so arrival order at
the hub is known. Each request's `seed` is a unique tag that the hub trace
(hubtrace.py) logs, joining the two.

One JSON line per request, times as time.time() on this host:
  send, hdr (status line in), tok (first content delta), end, status, code,
  retry_after, gen/ptok (the usage chunk), finish (finish_reason), timings
  (the engine's own: prompt_ms, predicted_per_second).
"""

from __future__ import annotations

import http.client
import json
import os
import sys
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
LAB = HERE.parents[4]
sys.path.insert(0, str(LAB / "tools" / "runs"))
import workload  # noqa: E402

STATE = Path(os.environ["STATE"])
HUB = os.environ.get("HUB") or (STATE / "hub.url").read_text().strip()
MODEL = "Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf"
TOKENS: dict[str, str] = json.loads((STATE / "secrets.json").read_text())["users"]
DRAWS = [workload.mkprompt() for _ in range(16)]  # UID 0..15, step 1's order
SHORT = "Count from 1 to 300, one number per line, nothing else."


def body(i: int | None, want: int, tag: int, prompt: str | None = None) -> bytes:
    if prompt is not None:
        messages = [{"role": "user", "content": prompt}]
    else:
        assert i is not None
        text, _ = DRAWS[i]
        messages = [
            {"role": "system", "content": workload.SYSTEM},
            {"role": "user", "content": text[len(workload.SYSTEM) :]},
        ]
    return json.dumps(
        {
            "model": MODEL,
            "messages": messages,
            "max_tokens": want,
            "temperature": 0,
            "seed": tag,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
    ).encode()


def one(spec: dict[str, Any], out: dict[str, Any]) -> None:
    """One request; a warm-up retries 503 model_loading after its Retry-After."""
    retries = 0
    while True:
        attempt(spec, out)
        if not (
            spec["cell"] == "warm"
            and out.get("status") == 503
            and out.get("code") == "model_loading"
            and retries < 100
        ):
            out["loading_retries"] = retries
            return
        retries += 1
        time.sleep(float(out.get("retry_after") or 5))
        out.clear()


def attempt(spec: dict[str, Any], out: dict[str, Any]) -> None:
    url = urllib.parse.urlsplit(HUB)
    conn = http.client.HTTPConnection(url.hostname, url.port, timeout=3600)
    out.update(spec)
    data = body(spec.get("uid"), spec["want"], spec["tag"], spec.get("prompt"))
    out.pop("prompt", None)
    out["send"] = time.time()
    try:
        conn.request(
            "POST",
            "/v1/chat/completions",
            body=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {TOKENS[spec['user']]}",
            },
        )
        if spec.get("hangup_after") is not None:
            time.sleep(spec["hangup_after"])
            out["hangup"] = time.time()
            conn.sock.shutdown(2)  # type: ignore[union-attr]
            conn.close()
            out["end"] = time.time()
            out["status"] = "client_closed"
            return
        resp = conn.getresponse()
        out["hdr"] = time.time()
        out["status"] = resp.status
        out["retry_after"] = resp.getheader("Retry-After")
        if resp.status != 200:
            raw = resp.read()
            out["end"] = time.time()
            try:
                err = json.loads(raw)["error"]
                out["code"], out["message"] = err.get("code"), err.get("message")
            except (ValueError, KeyError, TypeError):
                out["code"] = raw[:200].decode(errors="replace")
            return
        buf = b""
        chunks = 0
        while True:
            line = resp.readline()
            if not line:
                break
            line = line.strip()
            if not line.startswith(b"data:"):
                continue
            item = line[5:].strip()
            if item == b"[DONE]":
                break
            ev = json.loads(item)
            if "error" in ev:
                out["stream_error"] = ev["error"]
                break
            for ch in ev.get("choices") or []:
                piece = (ch.get("delta") or {}).get("content")
                if piece:
                    chunks += 1
                    now = time.time()
                    out.setdefault("tok", now)
                    out["last"] = now
                if ch.get("finish_reason"):
                    out["finish"] = ch["finish_reason"]
            if ev.get("usage"):
                out["gen"] = ev["usage"].get("completion_tokens")
                out["ptok"] = ev["usage"].get("prompt_tokens")
            if ev.get("timings"):
                t = ev["timings"]
                out["timings"] = {
                    k: t.get(k)
                    for k in (
                        "prompt_n",
                        "prompt_ms",
                        "predicted_n",
                        "predicted_ms",
                        "predicted_per_second",
                    )
                }
        del buf
        out["chunks"] = chunks
        out["end"] = time.time()
    except Exception as exc:  # a failed request is a row, not a crash
        out["end"] = time.time()
        out["status"] = out.get("status") or type(exc).__name__
        out["error"] = str(exc)[:200]
    finally:
        conn.close()


def specs(cell: str, run: str, args: dict[str, str]) -> list[dict[str, Any]]:
    base = int(time.time() * 1000) % 10**9 * 100
    out: list[dict[str, Any]] = []
    if cell == "warm":
        out = [{"user": "usr1", "uid": 0, "want": DRAWS[0][1]}]
    elif cell == "c4":
        out = [
            {"user": u, "uid": i, "want": DRAWS[i][1]}
            for u, i in zip(("usr1", "usr2", "usr3", "usr4"), range(4, 8), strict=True)
        ]
    elif cell == "c8":
        users = ("usr1", "usr2", "usr3", "usr4") * 2
        out = [
            {"user": u, "uid": i, "want": DRAWS[i][1]}
            for u, i in zip(users, range(4, 12), strict=True)
        ]
    elif cell == "burst":
        users = args.get("users", "usr1,usr2,usr3").split(",")
        per = int(args.get("per", "2"))
        want = int(args.get("want", "32"))
        out = [
            {"user": u, "uid": None, "want": want, "prompt": SHORT}
            for u in users
            for _ in range(per)
        ]
    elif cell == "long":
        out = [{"user": args.get("user", "usr1"), "uid": 3, "want": int(args["want"])}]
    elif cell == "hangup":
        out = [
            {
                "user": args.get("user", "usr2"),
                "uid": None,
                "want": 32,
                "prompt": SHORT,
                "hangup_after": float(args.get("after", "5")),
            }
        ]
    else:
        raise SystemExit(__doc__)
    for k, s in enumerate(out):
        s.update(run=run, cell=cell, k=k, tag=base + k)
    return out


def main(argv: list[str]) -> None:
    cell, run, label = argv[1], argv[2], argv[3]
    args = dict(a.split("=", 1) for a in argv[4:])
    gap = float(args.get("gap", "0.02"))
    todo = specs(cell, run, args)
    rows: list[dict[str, Any]] = [{} for _ in todo]
    threads = []
    for spec, row in zip(todo, rows, strict=True):
        spec["label"] = label
        th = threading.Thread(target=one, args=(spec, row), daemon=True)
        th.start()
        threads.append(th)
        time.sleep(gap)
    for th in threads:
        th.join()
    for row in rows:
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main(sys.argv)

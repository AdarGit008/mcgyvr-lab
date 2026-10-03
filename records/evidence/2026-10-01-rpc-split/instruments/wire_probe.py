#!/usr/bin/env python3
"""records/evidence/2026-10-01-rpc-split/instruments/wire_probe.py — requests against a head
llama-server whose RPC device is reached through rpcwire.py, one row per
request with what crossed the wire during it. Stdlib only; shipped to the head
and run there with ``python3 - ARGS``.

    python3 wire_probe.py PORT STATS_JSON CTL_JSON IFACE ARM...

ARM is ``label:kind:rtt_ms:mbit:max_tokens``; kind ``short`` sends a short
prompt, ``long`` a ~2k-token prompt (80 three-line functions). Every
request is temperature 0, ``ignore_eos`` (so the reply length is exactly max_tokens) and
``cache_prompt: false`` (so the prompt is evaluated every time). Each row
carries the server's own timings and the deltas of the relay's counters and of
the interface's byte counters (the interface also carries ssh and tailnet, so
the relay's figure is the RPC one).
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from typing import Any

SHORT = "Write a Python function that returns the n-th Fibonacci number iteratively."
LONG = "Explain what this code does, line by line.\n\n" + "\n".join(
    f"def f{i}(x):\n    y = x * {i} + {i * 7 % 13}\n    return y - {i}"
    for i in range(80)
)


def snap(stats_path: str, iface: str) -> dict[str, Any]:
    time.sleep(0.6)  # one relay housekeeping tick past the last byte
    with open(stats_path) as f:
        s: dict[str, Any] = json.load(f)
    for k in ("rx_bytes", "tx_bytes", "rx_packets", "tx_packets"):
        with open(f"/sys/class/net/{iface}/statistics/{k}") as f:
            s["if_" + k] = int(f.read())
    return s


def diff(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        k: b[k] - a[k] for k in b if isinstance(b[k], int) and k in a
    }
    for key in ("cmd_n", "cmd_bytes"):
        out[key] = {
            c: b[key][c] - a[key].get(c, 0)
            for c in b[key]
            if b[key][c] - a[key].get(c, 0)
        }
    return out


def main() -> None:
    port, stats_path, ctl_path, iface = sys.argv[1:5]
    for arm in sys.argv[5:]:
        label, kind, rtt, mbit, n = arm.split(":")
        with open(ctl_path, "w") as f:
            json.dump({"rtt_ms": float(rtt), "mbit": float(mbit)}, f)
        time.sleep(1.2)
        body = {
            "messages": [
                {"role": "user", "content": SHORT if kind == "short" else LONG}
            ],
            "temperature": 0,
            "seed": 42,
            "max_tokens": int(n),
            "ignore_eos": True,
            "cache_prompt": False,
        }
        a = snap(stats_path, iface)
        t0 = time.time()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3600) as r:
            resp = json.load(r)
        wall = time.time() - t0
        b = snap(stats_path, iface)
        t = resp.get("timings", {})
        print(
            json.dumps(
                {
                    "label": label,
                    "kind": kind,
                    "rtt_ms": float(rtt),
                    "mbit": float(mbit),
                    "wall_s": round(wall, 3),
                    "prompt_n": t.get("prompt_n"),
                    "prompt_ms": t.get("prompt_ms"),
                    "pp": t.get("prompt_per_second"),
                    "predicted_n": t.get("predicted_n"),
                    "predicted_ms": t.get("predicted_ms"),
                    "tg": t.get("predicted_per_second"),
                    "wire": diff(a, b),
                }
            ),
            flush=True,
        )
    with open(ctl_path, "w") as f:
        json.dump({"rtt_ms": 0, "mbit": 0}, f)


if __name__ == "__main__":
    main()

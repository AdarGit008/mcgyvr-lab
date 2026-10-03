#!/usr/bin/env python3
"""Recompute every reading of this record from its raw files.

  analyse.py EVIDENCE_DIR > analysis.txt   (also writes per-request.tsv)

Reads rows/*.jsonl (load.py), traces/hubtrace.jsonl (hubtrace.py),
traces/agenttrace-srv1.jsonl (agenttrace.py), args/*.txt (argcap.sh) and
clock.txt (clock.sh). Per request it joins the client's row to the hub's
events by tag (the request's seed) and to the head agent's events by the
relay's request id.

Definitions (times in s):
  latency     end - send, client clock
  ttft        first content delta - send, client clock (the client-side TTFT)
  queue       the hub's wait for a relay (q_exit.waited), 0 when admitted at once
  a_ttft      head agent: first content bytes from the head - the relay_request
              (rig clock; the agent-side TTFT, before its outbox and pump)
  flush       hub's first data frame - the agent's first data frame put in its
              outbox (cross-clock, corrected by clock.txt's offset)
  agg         sum of generated tokens / (last end - first send) of the cell,
              as step 1's driver computes it
  ptok, otok  the mean prompt and generated tokens per request (step 1's way)
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

EV = Path(sys.argv[1])
OUT_TSV = EV / "per-request.tsv"


def med(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None


def f(x: Any, nd: int = 2) -> str:
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def load_jsonl(p: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


offset = 0.0  # srv1 clock minus this host's
for line in (EV / "clock.txt").read_text().splitlines():
    m = re.search(r" srv1 rtt=[0-9.]+ms offset=([+-][0-9.]+)ms", line)
    if m:
        offset = float(m.group(1)) / 1000
        break

hub = load_jsonl(EV / "traces" / "hubtrace.jsonl")
agent = load_jsonl(EV / "traces" / "agenttrace-srv1.jsonl")
by_tag: dict[int, dict[str, Any]] = defaultdict(dict)
by_rid: dict[str, dict[str, Any]] = defaultdict(dict)
rid_of: dict[int, str] = {}
for e in hub:
    tag = e.get("tag")
    if e["ev"] == "relay_id":
        rid_of[tag] = e["rid"]
    elif e["ev"] in ("q_enter", "q_exit", "start", "start_end", "http_error"):
        if tag is not None:
            by_tag[tag].setdefault(e["ev"], e)
    elif e["ev"] == "frame":
        by_rid[e["rid"]].setdefault("h_" + e["kind"], e)
for e in agent:
    rid = e.get("rid")
    if rid is None:
        continue
    key = e["ev"] if e["ev"] != "a_frame" else "a_frame_" + e["kind"]
    by_rid[rid].setdefault(key, e)

rows: list[dict[str, Any]] = []
for p in sorted((EV / "rows").glob("*.jsonl")):
    for r in load_jsonl(p):
        r["file"] = p.name
        t = by_tag.get(r["tag"], {})
        rid = rid_of.get(r["tag"])
        a = by_rid.get(rid, {}) if rid else {}
        r["rid"] = rid
        r["latency"] = r["end"] - r["send"]
        r["ttft"] = r["tok"] - r["send"] if r.get("tok") else None
        r["queue"] = t["q_exit"]["waited"] if "q_exit" in t else None
        r["q_outcome"] = t["q_exit"]["outcome"] if "q_exit" in t else None
        r["admitted_at"] = t["q_exit"]["t"] if "q_exit" in t else None
        r["width"] = t["q_enter"]["width"] if "q_enter" in t else None
        r["http_error"] = t["http_error"]["status"] if "http_error" in t else None
        if "a_request" in a and "a_first_token" in a:
            r["a_ttft"] = a["a_first_token"]["t"] - a["a_request"]["t"]
        else:
            r["a_ttft"] = None
        if "a_frame_first_data" in a and "h_first_data" in a:
            r["flush"] = a["h_first_data"]["t"] - (
                a["a_frame_first_data"]["t"] - offset
            )
        else:
            r["flush"] = None
        if "a_request" in a and r.get("admitted_at"):
            r["hub_to_agent"] = (a["a_request"]["t"] - offset) - r["admitted_at"]
        else:
            r["hub_to_agent"] = None
        r["a_taken"] = a["a_request"].get("taken") if "a_request" in a else None
        r["h_end_code"] = a["h_end"].get("code") if "h_end" in a else None
        rows.append(r)

cols = [
    "label", "cell", "k", "user", "uid", "want", "status", "code", "retry_after",
    "send", "hdr", "tok", "end", "latency", "ttft", "queue", "q_outcome", "width",
    "a_ttft", "flush", "hub_to_agent", "gen", "ptok", "finish", "rid", "tag",
]
with OUT_TSV.open("w") as out:
    out.write("\t".join(cols) + "\n")
    for r in rows:
        out.write("\t".join(f(r.get(c), 3) for c in cols) + "\n")

print("# analysis.txt — recomputed by instruments/analyse.py from rows/, traces/, args/")
print(f"# srv1 clock offset used for `flush`: {offset * 1000:+.1f} ms (clock.txt)\n")

# --- launched argv per invocation ----------------------------------------------------
print("## Launched head per invocation (args/*.txt)\n")
argv_of: dict[str, str] = {}
for p in sorted((EV / "args").glob("*.txt")):
    for line in p.read_text().splitlines():
        if " head " in line and "llama-server" in line:
            m = re.search(r"-np (\d+) -c (\d+) .* -dev (\S+) -ts (\S+)", line)
            if m:
                argv_of[p.stem] = (
                    f"-np {m.group(1)} -c {m.group(2)} -dev {m.group(3)} -ts {m.group(4)}"
                )
        if "n_slots" in line:
            argv_of[p.stem] = argv_of.get(p.stem, "") + "  | " + line.split("load_model: ")[-1]
for k, v in argv_of.items():
    print(f"{k:<8} {v}")
print()

# --- throughput cells -----------------------------------------------------------------
cells: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
for r in rows:
    if r["label"].startswith("T") and r["cell"] in ("c4", "c8"):
        cells[(r["run"], r["cell"])].append(r)

summary: dict[tuple[str, str], dict[str, Any]] = {}
print("## Per invocation and cell (throughput campaign)\n")
hdr = (
    "| invocation | -np | cell | n | ok | agg tok/s | p50 latency | ttft p50 | "
    "queue p50 / max | a_ttft p50 | flush p50 | ptok | otok | at cap | non-200 |"
)
print(hdr)
print("|" + "---|" * 15)
for (run, cell), rs in sorted(cells.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    ok = [r for r in rs if r["status"] == 200 and not r.get("stream_error")]
    wall = max(r["end"] for r in rs) - min(r["send"] for r in rs)
    gen = sum(r.get("gen") or 0 for r in ok)
    agg = gen / wall
    s = {
        "run": run,
        "cell": cell,
        "np": rs[0].get("width"),
        "n": len(rs),
        "ok": len(ok),
        "agg": agg,
        "p50": med([r["latency"] for r in ok]),
        "ttft": med([r["ttft"] for r in ok if r["ttft"] is not None]),
        "queue": med([r["queue"] for r in ok if r["queue"] is not None]),
        "qmax": max((r["queue"] or 0) for r in ok) if ok else None,
        "a_ttft": med([r["a_ttft"] for r in ok if r["a_ttft"] is not None]),
        "flush": med([r["flush"] for r in ok if r["flush"] is not None]),
        "ptok": int(statistics.mean(r.get("ptok") or 0 for r in ok)) if ok else None,
        "otok": int(statistics.mean(r.get("gen") or 0 for r in ok)) if ok else None,
        "cap": sum(1 for r in ok if r.get("finish") == "length"),
        "bad": [f"{r['status']}:{r.get('code')}" for r in rs if r["status"] != 200],
    }
    summary[(run, cell)] = s
    print(
        f"| {run} | {s['np']} | {cell} | {s['n']} | {s['ok']} | {s['agg']:.2f} | "
        f"{f(s['p50'])} | {f(s['ttft'])} | {f(s['queue'])} / {f(s['qmax'])} | "
        f"{f(s['a_ttft'])} | {f(s['flush'])} | {s['ptok']} | {s['otok']} | "
        f"{s['cap']}/{s['ok']} | {','.join(s['bad']) or '-'} |"
    )
print()

# --- per arm: median [min-max], tie bar, verdict --------------------------------------
print("## Per arm (six invocations each: rounds a, b, c x arm and its null)\n")
arms = {"slots 4": ("T4-", "T4N-"), "slots 1": ("T1-", "T1N-")}
per_arm: dict[tuple[str, str], list[float]] = {}
print("| arm | cell | agg median [min-max] | spread | p50 latency | ttft p50 | queue p50 | a_ttft p50 | otok per invocation |")
print("|---|---|---|---|---|---|---|---|---|")
for cell in ("c4", "c8"):
    for arm, prefixes in arms.items():
        ss = [s for (run, c), s in summary.items() if c == cell and run.startswith(prefixes)]
        if not ss:
            continue
        aggs = [s["agg"] for s in ss]
        per_arm[(arm, cell)] = aggs
        spread = (max(aggs) - min(aggs)) / min(aggs)
        print(
            f"| {arm} | {cell} | {statistics.median(aggs):.2f} [{min(aggs):.2f}-{max(aggs):.2f}] "
            f"| {spread * 100:.1f}% | {f(med([s['p50'] for s in ss]))} | "
            f"{f(med([s['ttft'] for s in ss]))} | {f(med([s['queue'] for s in ss]))} | "
            f"{f(med([s['a_ttft'] for s in ss]))} | "
            f"{','.join(str(s['otok']) for s in sorted(ss, key=lambda s: s['run']))} |"
        )
print()
print("## Tie bar and verdict, slots 4 vs slots 1\n")
print(
    "Bar per cell = the larger of the two arms' spreads, (max - min) / min of agg over\n"
    "each arm's six invocations (arm and null together, as step 1 priced it).\n"
)
for cell in ("c4", "c8"):
    a4, a1 = per_arm.get(("slots 4", cell)), per_arm.get(("slots 1", cell))
    if not a4 or not a1:
        continue
    bar = max((max(a) - min(a)) / min(a) for a in (a4, a1))
    worst = min(a4) / max(a1) - 1
    print(
        f"{cell}: bar {bar * 100:.1f}%; worst slots-4 invocation {min(a4):.2f} vs best "
        f"slots-1 {max(a1):.2f}: {worst * 100:+.1f}% -> "
        f"{'slots 4 beats slots 1 beyond the bar in every invocation' if worst > bar else 'NOT resolved beyond the bar'}"
    )
    for r in "abc":
        for pre4, pre1 in (("T4-", "T1-"), ("T4N-", "T1N-")):
            s4, s1 = summary.get((pre4 + r, cell)), summary.get((pre1 + r, cell))
            if s4 and s1:
                print(
                    f"   round {r} {pre4}{r} {s4['agg']:.2f} vs {pre1}{r} {s1['agg']:.2f}: "
                    f"{(s4['agg'] / s1['agg'] - 1) * 100:+.1f}%"
                )
print()

# --- queue, order, cap -------------------------------------------------------------------
print("## Queue and order cells (chat_wait_slot_s 30)\n")
for r in rows:
    if r["label"].startswith("T"):
        continue
    print(
        f"{r['label']:<20} k={r['k']} {r['user']} status={r['status']} code={r.get('code')} "
        f"retry_after={r.get('retry_after')} send={r['send']:.2f} latency={r['latency']:.2f} "
        f"ttft={f(r['ttft'])} queue={f(r['queue'], 3)} q_outcome={r.get('q_outcome')} "
        f"http_error={r.get('http_error')} gen={r.get('gen')}"
    )
print()
print("## Order of service in the burst cells (the hub's admissions, in time order)\n")
for label in sorted({r["label"] for r in rows if r["cell"] == "burst" and "burst" in r["label"]}):
    rs = [r for r in rows if r["label"] == label and r.get("admitted_at")]
    arrival = [r["user"] for r in sorted(rs, key=lambda r: r["send"])]
    served = [r["user"] for r in sorted(rs, key=lambda r: r["admitted_at"])]
    print(f"{label}: arrival {' '.join(arrival)}")
    print(f"{' ' * len(label)}  served  {' '.join(served)}")
print()

print("## Rig cap: any `busy` from the head agent\n")
refused = [e for e in agent if e["ev"] == "a_request" and not e.get("taken")]
ends_busy = [e for e in hub if e["ev"] == "frame" and e.get("kind") == "end" and e.get("code") == "busy"]
client_502 = [r for r in rows if r["status"] == 502]
max_active = max((e.get("active", 0) for e in agent if e["ev"] == "a_request"), default=0)
print(f"agent relay_request refused (taken=false): {len(refused)} {[e.get('code') for e in refused]}")
print(f"hub relay_end frames with code busy: {len(ends_busy)}")
print(f"client 502 responses: {len(client_502)}")
print(f"agent relay_requests taken: {sum(1 for e in agent if e['ev'] == 'a_request' and e.get('taken'))}; most relays active at once on the head rig: {max_active}")
widths = defaultdict(int)
for e in hub:
    if e["ev"] == "q_exit" and e.get("outcome") == "admitted":
        widths[e.get("relays")] += 1
print(f"hub relays in use right after each admission (relays: count): {dict(sorted(widths.items()))}")
print()

# --- TTFT decomposition ---------------------------------------------------------------
print("## Time to first token, client side and agent side (throughput cells, ok rows)\n")
print("| arm | cell | client ttft p50 | queue p50 | hub->agent p50 | a_ttft p50 | flush p50 | engine prompt_ms p50 |")
print("|---|---|---|---|---|---|---|---|")
for cell in ("c4", "c8"):
    for arm, prefixes in arms.items():
        rs = [
            r for r in rows
            if r["cell"] == cell and r["label"].startswith(prefixes) and r["status"] == 200
        ]
        if not rs:
            continue
        pm = [r["timings"]["prompt_ms"] / 1000 for r in rs if r.get("timings")]
        print(
            f"| {arm} | {cell} | {f(med([r['ttft'] for r in rs if r['ttft']]))} | "
            f"{f(med([r['queue'] for r in rs if r['queue'] is not None]))} | "
            f"{f(med([r['hub_to_agent'] for r in rs if r['hub_to_agent'] is not None]), 3)} | "
            f"{f(med([r['a_ttft'] for r in rs if r['a_ttft'] is not None]))} | "
            f"{f(med([r['flush'] for r in rs if r['flush'] is not None]))} | {f(med(pm))} |"
        )

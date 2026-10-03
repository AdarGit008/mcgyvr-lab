"""pooled-slots: the per-rung table, the tie bar, GO/NO-GO and the round-trip
reading, recomputed from the round TSVs (round-a/b/c.tsv) alone.

    python analyse.py <envelope dir>

Reads rows the driver wrote (tools/runs/drivers/mgpu_sweep.py): CONFIG and
n=K rows per cell label, REQ rows per request. Nothing is read from prose.
"""

from __future__ import annotations

import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ENV = Path(sys.argv[1])
ROUNDS = ["round-a.tsv", "round-b.tsv", "round-c.tsv"]
RUNGS = (1, 2, 4)


def kv(fields: list[str]) -> dict[str, str]:
    out = {}
    for f in fields:
        if "=" in f:
            k, v = f.split("=", 1)
            out[k] = v
    return out


def load() -> tuple[dict, dict, dict]:
    level: dict[tuple[str, str], dict[int, dict[str, str]]] = defaultdict(dict)
    config: dict[tuple[str, str], dict[str, str]] = {}
    reqs: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    other: dict[tuple[str, str], list[tuple[str, list[str]]]] = defaultdict(list)
    for name in ROUNDS:
        p = ENV / name
        if not p.exists():
            continue
        rnd = name[6]
        for line in p.read_text().splitlines():
            if line.startswith("###") or not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            _, label, kind, *rest = parts
            tag = label.split()[0]
            if kind == "GPU":
                continue
            arm = tag.rsplit("-", 1)[0]
            key = (arm, rnd)
            if kind == "CONFIG":
                config[key] = kv(rest)
            elif kind.startswith("n="):
                level[key][int(kind[2:])] = kv(rest) | ({"ERR": "1"} if rest == ["ERR"] else {})
            elif kind == "REQ":
                reqs[key].append(kv(rest))
            else:
                other[key].append((kind, rest))
    return level, config, reqs, other


level, config, reqs, other = load()
rounds = sorted({r for _, r in level} | {r for _, r in other})
arms = []
for a, _ in list(level) + list(other):
    if a not in arms:
        arms.append(a)


def agg(arm: str, rnd: str, c: int) -> float | None:
    row = level.get((arm, rnd), {}).get(c)
    if not row or "agg" not in row:
        return None
    if not row.get("failed", "0/").startswith("0/"):
        return None  # a level with a failed request measured a failure, not a rate
    return float(row["agg"])


print("## per cell, per round: agg (tok/s) / p50 latency (s) / ttft_p50 / ptok / otok / early_stop / failed / slots")
for arm in arms:
    for rnd in rounds:
        cfg = config.get((arm, rnd), {})
        line = [f"{arm}-{rnd}", f"n_seq_max={cfg.get('n_seq_max','-')}",
                f"ctx_slot={cfg.get('real_ctx_slot','-')}", f"kvu={cfg.get('kv_unified','-')}",
                f"kv={cfg.get('kvbuf','-')}", f"comp={cfg.get('compbuf','-')}"]
        for kind, rest in other.get((arm, rnd), []):
            if kind not in ("PREFILL", "LOG"):
                line.append(f"{kind}:{' '.join(rest)[:160]}")
        print("  ".join(line))
        for c in RUNGS:
            row = level.get((arm, rnd), {}).get(c)
            if not row:
                continue
            if "agg" not in row:
                print(f"    n={c} {row}")
                continue
            print(f"    n={c} agg={row['agg']} p50={row['p50']} ttft={row['ttft_p50']} dec={row['dec']} "
                  f"ptok={row['ptok']} otok={row['otok']} early={row['early_stop']} failed={row['failed']} "
                  f"slots={row.get('slots','-')} wall={row['wall']}")

# Tie bar: per rung, the spread of agg over every invocation of the identical
# cell, S1 with S1N and S4 with S4N, as (max-min)/min; the bar at a rung is
# the larger of the two families' spreads.
print("\n## tie bar (split llama.cpp over RPC, priced from S1+S1N and S4+S4N)")
bar: dict[int, float] = {}
for c in RUNGS:
    spreads = {}
    for fam in (("S1", "S1N"), ("S4", "S4N")):
        xs = [agg(a, r, c) for a in fam for r in rounds]
        xs = [x for x in xs if x is not None]
        if len(xs) >= 2:
            spreads[fam[0]] = ((max(xs) - min(xs)) / min(xs), xs)
    bar[c] = max(s for s, _ in spreads.values()) if spreads else float("nan")
    for k, (s, xs) in spreads.items():
        print(f"  C={c} {k}-family n={len(xs)} agg={xs} spread={s*100:.1f}%")
    print(f"  C={c} bar={bar[c]*100:.1f}%")

print("\n## head-only null spreads (H1+H1N, H4+H4N)")
hbar: dict[int, float] = {}
for c in RUNGS:
    best = 0.0
    for fam in (("H1", "H1N"), ("H4", "H4N")):
        xs = [agg(a, r, c) for a in fam for r in rounds]
        xs = [x for x in xs if x is not None]
        if len(xs) >= 2:
            s = (max(xs) - min(xs)) / min(xs)
            best = max(best, s)
            print(f"  C={c} {fam[0]}-family agg={xs} spread={s*100:.1f}%")
    hbar[c] = best

print("\n## GO / NO-GO: S<C> agg against S1 agg, per round, at C=2 and C=4")
go = True
for c, arm in ((2, "S2"), (4, "S4")):
    for rnd in rounds:
        s1, sc = agg("S1", rnd, c), agg(arm, rnd, c)
        if s1 is None or sc is None:
            print(f"  C={c} round {rnd}: missing ({arm}={sc}, S1={s1})")
            go = False
            continue
        gain = sc / s1 - 1
        ok = gain > bar[c]
        go &= ok
        oa = level[(arm, rnd)][c]
        ob = level[("S1", rnd)][c]
        match = (oa["ptok"], oa["otok"]) == (ob["ptok"], ob["otok"])
        print(f"  C={c} round {rnd}: {arm}={sc} S1={s1} gain={gain*100:+.1f}% bar={bar[c]*100:.1f}% beats={ok} "
              f"ptok/otok {arm}={oa['ptok']}/{oa['otok']} S1={ob['ptok']}/{ob['otok']} match={match}")
    # conservative: weakest SC against strongest S1-family invocation
    scs = [x for x in (agg(arm, r, c) for r in rounds) if x is not None]
    s1s = [x for x in (agg(a, r, c) for a in ("S1", "S1N") for r in rounds) if x is not None]
    if scs and s1s:
        print(f"  C={c} min({arm})={min(scs)} vs max(S1,S1N)={max(s1s)} gain={(min(scs)/max(s1s)-1)*100:+.1f}%")
print(f"  reading: {'GO' if go else 'NO-GO'}")

print("\n## open prediction: split penalty agg(S)/agg(H) at the same -np, per rung")
for c in RUNGS:
    for k in (1, 2, 4):
        ratios = []
        for rnd in rounds:
            s, h = agg(f"S{k}", rnd, c), agg(f"H{k}", rnd, c)
            if s and h:
                ratios.append(s / h)
        if ratios:
            print(f"  C={c} np={k} S/H per round={['%.3f' % r for r in ratios]} mean={statistics.mean(ratios):.3f}")

print("\n## ptok/otok match across arms at each rung (comparable rows only)")
for c in RUNGS:
    seen = defaultdict(list)
    for (arm, rnd), rows in level.items():
        row = rows.get(c)
        if row and "ptok" in row:
            seen[(row["ptok"], row["otok"])].append(f"{arm}-{rnd}")
    for k, v in sorted(seen.items(), key=lambda kv: -len(kv[1])):
        print(f"  C={c} ptok,otok={k}: {len(v)} rows: {' '.join(sorted(v))}")


print("\n## markdown: per cell and rung over the rounds (agg median [min-max] over invocations without a failed request)")
print("| cell | config | -np | ctx/slot (n_ctx_seq) | C | agg tok/s | p50 latency s | ttft_p50 s | invocations | otok |")
print("|---|---|---|---|---|---|---|---|---|---|")
for arm in arms:
    cfgs = [config.get((arm, r), {}) for r in rounds if (arm, r) in config]
    if not cfgs:
        continue
    cfg_tag = "split" if "RPC0" in cfgs[0].get("kvbuf", "") else "head-only"
    for c in RUNGS:
        rows = [level.get((arm, r), {}).get(c) for r in rounds]
        rows = [x for x in rows if x and "agg" in x]
        good = [x for x in rows if x.get("failed", "0/").startswith("0/")]
        if not rows:
            continue
        if good:
            aggs = sorted(float(x["agg"]) for x in good)
            p50s = [float(x["p50"]) for x in good]
            tts = [float(x["ttft_p50"]) for x in good]
            a = f"{statistics.median(aggs):.1f} [{aggs[0]:.1f}-{aggs[-1]:.1f}]"
            p = f"{statistics.median(p50s):.2f}"
            t = f"{statistics.median(tts):.2f}"
        else:
            a = p = t = "-"
        bad = len(rows) - len(good)
        otoks = ",".join(sorted({x["otok"] for x in good}))
        print(f"| {arm} | {cfg_tag} | {cfgs[0].get('n_seq_max')} | {cfgs[0].get('real_ctx_slot')}"
              f"{' (kvu)' if cfgs[0].get('kv_unified') == 'true' else ''} | {c} | {a} | {p} | {t} | "
              f"{len(good)}{f' (+{bad} with failed requests)' if bad else ''} | {otoks} |")


def req_view(arm: str, rnd: str, c: int) -> list[dict[str, str]]:
    return [r for r in reqs.get((arm, rnd), []) if r.get("n") == str(c)]


def num(x: str | None) -> float | None:
    try:
        return float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


print("\n## desk read cells")
print("### cell 1 (-c 12288 total) and cell 2 (-kvu): the engine's own lines")
for arm in ("S2", "S4", "D1S2", "D1S4", "D2KVU", "D2FILL"):
    for rnd in rounds:
        cfg = config.get((arm, rnd))
        if cfg:
            print(f"  {arm}-{rnd}: n_seq_max={cfg.get('n_seq_max')} n_ctx_seq={cfg.get('real_ctx_slot')} "
                  f"kv_unified={cfg.get('kv_unified')} kvbuf={cfg.get('kvbuf')} compbuf={cfg.get('compbuf')} "
                  f"vram={cfg.get('vram')}")
        for kind, rest in other.get((arm, rnd), []):
            if kind not in ("PREFILL", "LOG", "CONFIG"):
                print(f"  {arm}-{rnd}: {kind} {' '.join(rest)[:300]}")
print("### requests that carried an error, or a status other than 200")
for (arm, rnd), rows in sorted(reqs.items()):
    for r in rows:
        if r.get("err") or r.get("status") != "200":
            print(f"  {arm}-{rnd} n={r['n']} i={r['i']} status={r.get('status')} gen={r.get('gen')} "
                  f"tok={r.get('tok')} end={r.get('end')} err={r.get('err', '')[:120]}")
print("### cell 3: the held request (S1 with @stagger=0.5)")
for rnd in rounds:
    for c in (2, 4):
        rows = req_view("D3HELD", rnd, c)
        if not rows:
            continue
        order_send = [r["i"] for r in sorted(rows, key=lambda r: num(r["send"]) or 0)]
        order_tok = [r["i"] for r in sorted(rows, key=lambda r: num(r["tok"]) or 1e9)]
        print(f"  D3HELD-{rnd} C={c} arrival={order_send} first-token order={order_tok} "
              f"fifo={order_send == order_tok}")
        for r in rows:
            gap = (num(r["tok"]) or 0) - (num(r["byte"]) or 0)
            print(f"    i={r['i']} send={r['send']} byte={r['byte']} tok={r['tok']} end={r['end']} "
                  f"status={r['status']} byte_before_tok={gap:.3f}s gen={r['gen']}")
print("### cells 4-7 against their controls: agg, dec, and per-request tpot ms ((end-tok)/(gen-1))")
pairs = [("D4GAP", "D4SEQ", 2), ("D5STAG", "S4", 2), ("D5STAG", "S4", 4), ("D6OUT1", "S4", 2),
         ("D6OUT1", "S4", 4), ("D7NOCACHE", "S2", 4)]
for a, b, c in pairs:
    for rnd in rounds:
        out = []
        for arm in (a, b):
            row = level.get((arm, rnd), {}).get(c, {})
            tp = [((num(r["end"]) or 0) - (num(r["tok"]) or 0)) / (int(r["gen"]) - 1) * 1000
                  for r in req_view(arm, rnd, c) if num(r["tok"]) is not None and int(r["gen"]) > 1]
            out.append(f"{arm}: agg={row.get('agg')} dec={row.get('dec')} otok={row.get('otok')} "
                       f"wall={row.get('wall')} slots={row.get('slots')} req_tpot_ms={[round(t) for t in tp]}")
        print(f"  C={c} round {rnd}: " + " | ".join(out))

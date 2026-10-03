#!/usr/bin/env python3
"""P1: one Jev candidate over the labelled slice, through the real primitive.

Usage: p1_run.py BASE_URL MODEL TAG SLICE.jsonl OUT.jsonl [--kwargs JSON]

Per row: `decision.classify` (the product's code path, one request per
question, max_tokens=1, temperature 0, logprobs) with gate/jev.py's three
questions over state_jev, then verify.py's VERDICT_QUESTION over
state_verdict. Records p(Yes) per Noul, expected level per Score, wall per
question, prompt tokens, DecisionError if any. Prints a summary line with
accuracy@0.5, AUROC, Brier, ECE(10) for satisfies_task and verdict against
label (gate passed).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, "/tmp/claude-1000/-home-adaramir/15b6132f-a502-4a0c-9d7f-4c7b9b894f37/scratchpad/wt/mc-run/src")
from mcgyvr import decision as dec  # noqa: E402
from mcgyvr.gate.jev import JEV_QUESTIONS  # noqa: E402
from mcgyvr.verify import VERDICT_KEY, VERDICT_QUESTION  # noqa: E402


def auroc(scores: list[float], labels: list[int]) -> float | None:
    pos = [s for s, y in zip(scores, labels) if y == 1]
    neg = [s for s, y in zip(scores, labels) if y == 0]
    if not pos or not neg:
        return None
    wins = 0.0
    for p in pos:
        for n in neg:
            wins += 1.0 if p > n else 0.5 if p == n else 0.0
    return wins / (len(pos) * len(neg))


def ece(scores: list[float], labels: list[int], bins: int = 10) -> float:
    total = len(scores)
    e = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, s in enumerate(scores) if (lo <= s < hi) or (b == bins - 1 and s == 1.0)]
        if not idx:
            continue
        conf = sum(scores[i] for i in idx) / len(idx)
        acc = sum(labels[i] for i in idx) / len(idx)
        e += len(idx) / total * abs(conf - acc)
    return e


def summarize(name: str, scores: list[float], labels: list[int]) -> dict:
    n = len(scores)
    if n == 0:
        return {"q": name, "n": 0}
    acc = sum(1 for s, y in zip(scores, labels) if (s >= 0.5) == (y == 1)) / n
    brier = sum((s - y) ** 2 for s, y in zip(scores, labels)) / n
    yes_rate = sum(1 for s in scores if s >= 0.5) / n
    return {
        "q": name,
        "n": n,
        "acc": round(acc, 3),
        "auroc": None if (a := auroc(scores, labels)) is None else round(a, 3),
        "brier": round(brier, 3),
        "ece10": round(ece(scores, labels), 3),
        "yes_rate": round(yes_rate, 3),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base_url")
    ap.add_argument("model")
    ap.add_argument("tag")
    ap.add_argument("slice")
    ap.add_argument("out")
    ap.add_argument("--kwargs", default="")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    endpoint = SimpleNamespace(base_url=args.base_url, credential=lambda: None)
    rows = [json.loads(l) for l in open(args.slice)]
    if args.limit:
        rows = rows[: args.limit]
    out = open(args.out, "w")
    sat, ver, lab, lat, risk = [], [], [], [], []
    errors = 0
    t_all = time.perf_counter()
    for r in rows:
        rec = {"tag": args.tag, "id": r["id"], "task": r["task"], "model_src": r["model"], "label": r["label"]}
        t0 = time.perf_counter()
        try:
            d1 = dec.classify(endpoint, args.model, r["state_jev"], JEV_QUESTIONS, timeout_s=600)
            d2 = dec.classify(endpoint, args.model, r["state_verdict"], {VERDICT_KEY: VERDICT_QUESTION}, timeout_s=600)
        except Exception as exc:
            rec["error"] = f"{type(exc).__name__}: {exc}"[:300]
            errors += 1
            out.write(json.dumps(rec) + "\n")
            out.flush()
            continue
        rec["wall_s"] = round(time.perf_counter() - t0, 3)
        a = d1.answers
        rec["satisfies_task_p"] = round(a["satisfies_task"].probability_true, 4)
        rec["in_scope_p"] = round(a["in_scope"].probability_true, 4)
        rec["regression_level"] = round(a["regression_risk"].level, 4)
        rec["verdict_p"] = round(d2.answers[VERDICT_KEY].probability_true, 4)
        rec["n_added"] = len(r["state_jev"]["added_lines"])
        out.write(json.dumps(rec) + "\n")
        out.flush()
        sat.append(rec["satisfies_task_p"])
        ver.append(rec["verdict_p"])
        risk.append(rec["regression_level"])
        lab.append(r["label"])
        lat.append(rec["wall_s"])
    lat.sort()
    summary = {
        "tag": args.tag,
        "rows": len(rows),
        "errors": errors,
        "wall_total_s": round(time.perf_counter() - t_all, 1),
        "wall_per_row_med_s": round(lat[len(lat) // 2], 3) if lat else None,
        "wall_per_row_p90_s": round(lat[int(len(lat) * 0.9)], 3) if lat else None,
        "satisfies_task": summarize("satisfies_task", sat, lab),
        "verdict": summarize("verdict", ver, lab),
        "regression_level_mean_pass": round(sum(x for x, y in zip(risk, lab) if y) / max(1, sum(lab)), 3) if lab else None,
        "regression_level_mean_fail": round(sum(x for x, y in zip(risk, lab) if not y) / max(1, len(lab) - sum(lab)), 3) if lab else None,
    }
    out.write(json.dumps({"summary": summary}) + "\n")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

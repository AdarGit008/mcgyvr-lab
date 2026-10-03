#!/usr/bin/env python3
"""The labelled slice for the Jev ladder: keys and labels, never content.

Reads records/measurements/*/bench-py/results.jsonl (the shipped gate's rows,
tools/bench/score.py) and writes one JSON line per chosen row with the keys
that re-derive its state — run, task, arm, draw — and its label. The state
itself (contract task, target, the candidate's added lines) is derived by
jev_slice.py at run time from the same records, so the slice carries no copy
of anything the records already hold.

Strata: positive = ``passed`` True; negative = ``rejected_by == "acceptance"``
(lint, format, syntax passed; the tests failed — the semantic case a Jev
question is asked to see). One row per task first, then fill; seeded.

    python tools/runs/campaigns/jev-mcorch/build_slice.py OUT.jsonl \
        [--per-class N] [--seed S]

Reaches no rig and no network.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def rows(lab: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    pos: list[dict[str, object]] = []
    neg: list[dict[str, object]] = []
    for results in sorted(lab.glob("records/measurements/*/bench-py/results.jsonl")):
        run = results.parent
        for line in results.read_text(encoding="utf-8").splitlines():
            d = json.loads(line)
            if d.get("parse_error") or d.get("stop_reason") not in (None, "complete"):
                continue
            cand = run / "candidates" / d["task"] / f"{d['arm']}-{d['draw']}.txt"
            contract = lab / "tools/bench/tasks/py" / d["task"] / "contract.yaml"
            if not cand.is_file() or not contract.is_file():
                continue
            rec: dict[str, object] = {
                "run": run.parent.name,
                "task": d["task"],
                "type": d["type"],
                "model": d["model"],
                "arm": d["arm"],
                "draw": d["draw"],
                "rejected_by": d.get("rejected_by"),
            }
            if d["passed"] is True:
                rec["label"] = 1
                pos.append(rec)
            elif d.get("rejected_by") == "acceptance":
                rec["label"] = 0
                neg.append(rec)
    return pos, neg


def pick(
    pool: list[dict[str, object]], n: int, rng: random.Random
) -> list[dict[str, object]]:
    rng.shuffle(pool)
    seen: set[object] = set()
    chosen: list[dict[str, object]] = []
    rest: list[dict[str, object]] = []
    for r in pool:
        if r["task"] not in seen and len(chosen) < n:
            seen.add(r["task"])
            chosen.append(r)
        else:
            rest.append(r)
    return chosen + rest[: max(0, n - len(chosen))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--per-class", type=int, default=40)
    ap.add_argument("--seed", type=int, default=20261003)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    pos, neg = rows(REPO)
    chosen = pick(pos, args.per_class, rng) + pick(neg, args.per_class, rng)
    rng.shuffle(chosen)
    with open(args.out, "w", encoding="utf-8") as out:
        out.write(
            json.dumps(
                {
                    "_provenance": "tools/runs/campaigns/jev-mcorch/build_slice.py",
                    "seed": args.seed,
                    "per_class": args.per_class,
                    "pool_pos": len(pos),
                    "pool_neg": len(neg),
                    "label": "bench rows: passed (1) or rejected_by=acceptance (0)",
                }
            )
            + "\n"
        )
        for i, r in enumerate(chosen):
            r["id"] = f"s{i:03d}"
            out.write(json.dumps(r) + "\n")
    print(
        f"pool {len(pos)} pos / {len(neg)} neg -> {len(chosen)} rows, "
        f"{len({r['task'] for r in chosen})} tasks",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

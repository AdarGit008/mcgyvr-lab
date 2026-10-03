#!/usr/bin/env python3
"""Build the P1 labelled slice for the Jev accuracy pilot.

Source: lab records/measurements/*/bench-py/results.jsonl rows, joined to
<run>/bench-py/candidates/<task>/<arm>-<draw>.txt and to
tools/bench/tasks/py/<task>/contract.yaml. Label = the shipped gate's `passed`
(tools/bench/score.py). Positive stratum: passed=True. Negative stratum:
rejected_by == "acceptance" (lint/format/syntax passed, tests failed — the
semantic case Jev is asked to see). The state is built the way
src/mcgyvr/gate/jev.py:build_state does: task, path, added_lines of the
candidate against target_content (difflib, added lines only).

Usage: build_slice.py LAB_ROOT OUT.jsonl [--per-class N] [--seed S]
"""

from __future__ import annotations

import argparse
import difflib
import glob
import json
import random
from pathlib import Path

import yaml


def added_lines(original: str, change: str) -> list[dict]:
    out = []
    sm = difflib.SequenceMatcher(a=original.splitlines(), b=change.splitlines(), autojunk=False)
    new = change.splitlines()
    for tag, _i1, _i2, j1, j2 in sm.get_opcodes():
        if tag in ("insert", "replace"):
            for j in range(j1, j2):
                out.append({"line": j + 1, "text": new[j]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lab")
    ap.add_argument("out")
    ap.add_argument("--per-class", type=int, default=40)
    ap.add_argument("--seed", type=int, default=20261003)
    args = ap.parse_args()
    lab = Path(args.lab)
    rng = random.Random(args.seed)
    pos, neg = [], []
    for f in sorted(glob.glob(str(lab / "records/measurements/*/bench-py/results.jsonl"))):
        run = Path(f).parent
        for line in open(f):
            d = json.loads(line)
            if d.get("parse_error"):
                continue
            if d.get("stop_reason") not in (None, "complete"):
                continue
            cand = run / "candidates" / d["task"] / f"{d['arm']}-{d['draw']}.txt"
            if not cand.is_file():
                continue
            contract = lab / "tools/bench/tasks/py" / d["task"] / "contract.yaml"
            if not contract.is_file():
                continue
            rec = {
                "run": run.parent.name,
                "task": d["task"],
                "type": d["type"],
                "model": d["model"],
                "arm": d["arm"],
                "draw": d["draw"],
                "passed": d["passed"],
                "rejected_by": d.get("rejected_by"),
                "candidate": str(cand.relative_to(lab)),
                "contract": str(contract.relative_to(lab)),
            }
            if d["passed"] is True:
                pos.append(rec)
            elif d.get("rejected_by") == "acceptance":
                neg.append(rec)

    def pick(pool: list[dict], n: int) -> list[dict]:
        # spread across tasks: one per task first, then fill
        rng.shuffle(pool)
        seen, chosen, rest = set(), [], []
        for r in pool:
            if r["task"] not in seen and len(chosen) < n:
                seen.add(r["task"])
                chosen.append(r)
            else:
                rest.append(r)
        chosen += rest[: max(0, n - len(chosen))]
        return chosen

    rows = pick(pos, args.per_class) + pick(neg, args.per_class)
    rng.shuffle(rows)
    with open(args.out, "w") as out:
        for i, r in enumerate(rows):
            c = yaml.safe_load(open(lab / r["contract"]))
            change = open(lab / r["candidate"]).read()
            original = c.get("target_content", "") or ""
            r["id"] = f"s{i:03d}"
            r["label"] = 1 if r["passed"] else 0
            r["state_jev"] = {
                "task": c["task"],
                "path": c["target"],
                "added_lines": added_lines(original, change),
            }
            r["state_verdict"] = {
                "task_type": c["task_type"],
                "task": c["task"],
                "target": c["target"],
                "interface": c.get("interface", ""),
                "deterministic_gate": "not run",
                "original": original,
                "change": change,
            }
            out.write(json.dumps(r) + "\n")
    print(
        f"pos pool {len(pos)} neg pool {len(neg)} -> wrote {len(rows)} rows "
        f"({sum(r['label'] for r in rows)} pass, {sum(1-r['label'] for r in rows)} fail), "
        f"tasks {len({r['task'] for r in rows})}, models {sorted({r['model'] for r in rows})}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

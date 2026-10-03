#!/usr/bin/env python3
"""Step 4's corpus: one tiny git repository per bench task, truth beside it.

    make_repos.py OUT_DIR TASK_ID [TASK_ID...]

Each repo holds the task's stub (``target`` written from the contract's
``target_content``) and ``accept.py``, committed, and a ``.truth.json``
{task, target, task_type, interface, acceptance} that orch_modes.py reads for
the prompt and the scoring and removes from the clone it hands a mode. The
reference solution is NOT copied: a repo that holds the answer measures
nothing. Reaches no rig and no network; ``git`` is the only program run.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[4]
TASKS = REPO / "tools/bench/tasks/py"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("tasks", nargs="+")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for task in args.tasks:
        src = TASKS / task
        contract = yaml.safe_load((src / "contract.yaml").read_text(encoding="utf-8"))
        dst = out / task
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir()
        (dst / contract["target"]).write_text(contract.get("target_content") or "")
        shutil.copy(src / "accept.py", dst / "accept.py")
        (dst / ".truth.json").write_text(
            json.dumps(
                {
                    "task": contract["task"],
                    "target": contract["target"],
                    "task_type": contract["task_type"],
                    "interface": contract.get("interface", ""),
                    # -B: the gate's preflight refuses an acceptance command that
                    # writes to the tree, and `python accept.py` writes __pycache__
                    # `mcgyvr run` preflight: acceptance must be GREEN on the
                    # unchanged tree and read-only (-B: no __pycache__); the
                    # task's accept.py fails until the work is done, so it is
                    # the `demonstration` (fails before, passes after)
                    "acceptance": [
                        f"python -B -c 'import {Path(contract['target']).stem}'"
                    ],
                    "demonstration": [
                        a.replace("python accept.py", "python -B accept.py")
                        for a in (
                            contract.get("acceptance", [])
                            or contract.get("demonstration", [])
                        )
                    ],
                }
            )
        )
        git = ["git", "-c", "user.email=jev@mcorch", "-c", "user.name=jev-mcorch"]
        subprocess.run([*git, "init", "-q"], cwd=dst, check=True)
        subprocess.run(
            [*git, "add", contract["target"], "accept.py"], cwd=dst, check=True
        )
        subprocess.run(
            [*git, "commit", "-q", "-m", f"bench task {task}"], cwd=dst, check=True
        )
        print(
            f"{dst}: {contract['task_type']} -> {contract['target']}", file=sys.stderr
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

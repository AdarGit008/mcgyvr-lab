#!/usr/bin/env python3
"""Steps 4/6/7's corpus: one git repository per task, truth beside it.

    make_repos.py OUT_DIR TASK_ID [TASK_ID...] [--real NAME=PATH]

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
REAL_TASKS = Path(__file__).resolve().parent / "real-tasks.json"
GIT = ["git", "-c", "user.email=jev@mcorch", "-c", "user.name=jev-mcorch"]
GITIGNORE = "__pycache__/\n*.pyc\n.mcgyvr/\n"


def real_repos(out: Path, name: str, src: Path) -> None:
    """One copy of the read-only clone per task in real-tasks.json[name]."""
    spec = json.loads(REAL_TASKS.read_text(encoding="utf-8"))
    tasks = spec.get(name)
    if not tasks:
        raise SystemExit(f"make_repos: real-tasks.json names no tasks for {name!r}")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=src,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    for task in tasks:
        dst = out / f"{name}-{task['id']}"
        if dst.exists():
            shutil.rmtree(dst)
        subprocess.run(
            ["git", "clone", "-q", "--no-hardlinks", str(src), str(dst)], check=True
        )
        subprocess.run([*GIT, "checkout", "-q", head], cwd=dst, check=True)
        (dst / ".truth.json").write_text(
            json.dumps(
                {
                    **{
                        k: task[k]
                        for k in (
                            "task",
                            "target",
                            "task_type",
                            "interface",
                            "acceptance",
                            "demonstration",
                        )
                    },
                    "source": f"{name}@{head[:12]}",
                }
            )
        )
        print(
            f"{dst}: {task['task_type']} -> {task['target']} ({name}@{head[:12]})",
            file=sys.stderr,
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("tasks", nargs="*")
    ap.add_argument(
        "--real", action="append", default=[], help="NAME=PATH of a read-only clone"
    )
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for real in args.real:
        name, _, path = real.partition("=")
        real_repos(out, name, Path(path))
    for task in args.tasks:
        src = TASKS / task
        contract = yaml.safe_load((src / "contract.yaml").read_text(encoding="utf-8"))
        dst = out / task
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir()
        (dst / contract["target"]).write_text(contract.get("target_content") or "")
        shutil.copy(src / "accept.py", dst / "accept.py")
        (dst / ".gitignore").write_text(GITIGNORE)
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
        subprocess.run([*GIT, "init", "-q"], cwd=dst, check=True)
        subprocess.run(
            [*GIT, "add", contract["target"], "accept.py", ".gitignore"],
            cwd=dst,
            check=True,
        )
        subprocess.run(
            [*GIT, "commit", "-q", "-m", f"bench task {task}"], cwd=dst, check=True
        )
        print(
            f"{dst}: {contract['task_type']} -> {contract['target']}", file=sys.stderr
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

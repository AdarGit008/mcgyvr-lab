#!/usr/bin/env python3
"""P2: orchestrator modes D / P / J on tiny repos, one local model.

Usage: p2_run.py CFG_DIR REPOS_DIR OUT.jsonl TAG [--modes D,P,J] [--run]

  D  direct: chat-completion with skills/mcgyvr/SKILL.md (the schema) + the
     repo's file list and contents in context; the reply's ```yaml block is
     written to a file and validated with `mcgyvr contract`. What the API-tier
     agent does today, done by the local rung.
  P  prose delegate: `mcgyvr delegate PROMPT REPO --output DIR` (proposer_for).
  J  Jev ClassifierProposer: delegate.classifier_proposer_for through
     orchestrator.decompose (NOT wired to the CLI; this harness wires it).

Each repo holds .truth.json {task, target, task_type, interface, acceptance}.
The prompt is truth.task. Scored: contracts emitted, valid, target match,
task_type match, wall, tokens (D: usage; P/J: /metrics not read — wall only),
and with --run the `mcgyvr run` outcome per contract (tempdir sandbox).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

MC = Path("/tmp/claude-1000/-home-adaramir/15b6132f-a502-4a0c-9d7f-4c7b9b894f37/scratchpad/wt/mc-run")
sys.path.insert(0, str(MC / "src"))


def sh(cmd: list[str], env: dict | None = None, cwd: str | None = None, timeout: int = 1800) -> subprocess.CompletedProcess:
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run(cmd, capture_output=True, text=True, env=e, cwd=cwd, timeout=timeout)


def mcgyvr(args: list[str], cfg: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    return sh(["uv", "run", "--no-sync", "mcgyvr", *args], env={"MCGYVR_CONFIG": cfg}, cwd=str(MC) if cwd is None else cwd)


def repo_listing(repo: Path) -> str:
    parts = []
    for p in sorted(repo.rglob("*")):
        if ".git" in p.parts or p.name.startswith(".truth") or not p.is_file():
            continue
        text = p.read_text(errors="replace")
        parts.append(f"### {p.relative_to(repo)}\n```\n{text}\n```")
    return "\n\n".join(parts)


def mode_d(cfg_unit_url: str, model: str, repo: Path, prompt: str, skill: str, out_dir: Path) -> dict:
    system = (
        "You are the mcgyvr orchestrator. Author exactly ONE task contract as YAML "
        "for the request, following the schema below. Reply with a single ```yaml "
        "block and nothing else. The contract must set task_type, id, task, target, "
        "scope.allow, stop_conditions, acceptance (the repo's test command if there is "
        "one) and limits.max_output_tokens.\n\n" + skill
    )
    user = f"REPOSITORY FILES:\n\n{repo_listing(repo)}\n\nREQUEST:\n{prompt}\n\nWrite the contract."
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.0,
        "max_tokens": 2048,
        "stream": False,
    }
    req = urllib.request.Request(cfg_unit_url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=1800) as resp:
        doc = json.loads(resp.read())
    wall = time.perf_counter() - t0
    text = doc["choices"][0]["message"].get("content") or ""
    usage = doc.get("usage", {})
    m = re.search(r"```(?:yaml|yml)?\s*\n(.*?)```", text, re.S)
    yaml_text = m.group(1) if m else text
    path = out_dir / "D-contract.yaml"
    path.write_text(yaml_text)
    v = mcgyvr(["contract", str(path)], cfg="")
    rec = {
        "wall_s": round(wall, 2),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "valid": v.returncode == 0,
        "validate_err": (v.stderr or v.stdout)[-400:] if v.returncode else "",
        "contracts": [str(path)] if v.returncode == 0 else [],
        "reply_head": text[:300],
    }
    if v.returncode == 0:
        import yaml

        c = yaml.safe_load(yaml_text)
        rec["emitted"] = [{"id": c.get("id"), "task_type": c.get("task_type"), "target": c.get("target")}]
    return rec


def mode_p(cfg: str, repo: Path, prompt: str, out_dir: Path) -> dict:
    d = out_dir / "P"
    d.mkdir(exist_ok=True)
    t0 = time.perf_counter()
    r = mcgyvr(["delegate", prompt, str(repo), "--output", str(d)], cfg=cfg)
    wall = time.perf_counter() - t0
    files = sorted(d.glob("*.json"))
    emitted = []
    for f in files:
        c = json.loads(f.read_text())
        emitted.append({"id": c.get("id"), "task_type": c.get("task_type"), "target": c.get("target")})
    return {
        "wall_s": round(wall, 2),
        "rc": r.returncode,
        "stderr_tail": r.stderr[-600:],
        "contracts": [str(f) for f in files],
        "emitted": emitted,
        "valid": bool(files),
    }


def mode_j(cfg: str, repo: Path, prompt: str, out_dir: Path) -> dict:
    from mcgyvr.config import load as load_config
    from mcgyvr.delegate import classifier_proposer_for
    from mcgyvr.orchestrator import attach, build_index, decompose
    from mcgyvr.pool import source_map

    config = load_config(Path(cfg))
    pool = source_map(config)
    propose = classifier_proposer_for(pool)
    assert propose is not None
    d = out_dir / "J"
    d.mkdir(exist_ok=True)
    t0 = time.perf_counter()
    with attach(str(repo)) as r:
        index = build_index(r.root)
        dec = decompose(index, prompt, propose=propose, config=config)
    wall = time.perf_counter() - t0
    files = []
    emitted = []
    for contract, document in zip(dec.contracts, dec.documents, strict=True):
        p = d / f"{contract.id}.json"
        p.write_text(json.dumps(document, indent=2))
        files.append(str(p))
        emitted.append({"id": contract.id, "task_type": contract.task_type, "target": contract.target})
    return {
        "wall_s": round(wall, 2),
        "contracts": files,
        "emitted": emitted,
        "refusals": [str(x) for x in dec.refusals][:5],
        "refused": not files,
        "valid": bool(files),
    }


def run_contract(cfg: str, contract: str, repo: Path, out_dir: Path) -> dict:
    result = out_dir / (Path(contract).stem + ".result.json")
    t0 = time.perf_counter()
    r = mcgyvr(["run", contract, "--repo", str(repo), "--sandbox", "tempdir", "--orchestrator", "p2-pilot", "--result", str(result)], cfg=cfg)
    wall = time.perf_counter() - t0
    rec = {"contract": contract, "rc": r.returncode, "wall_s": round(wall, 1), "stderr_tail": r.stderr[-400:]}
    if result.is_file():
        doc = json.loads(result.read_text())
        rec["outcome"] = doc.get("outcome")
        rec["attempts"] = [{"rung": a.get("rung"), "verdict": a.get("verdict"), "detail": (a.get("detail") or "")[:200]} for a in doc.get("attempts", [])]
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cfg")
    ap.add_argument("repos")
    ap.add_argument("out")
    ap.add_argument("tag")
    ap.add_argument("--modes", default="D,P,J")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--unit-url", default="http://srv1:8080")
    ap.add_argument("--model", default="orch")
    args = ap.parse_args()
    skill = (MC / "skills/mcgyvr/SKILL.md").read_text()
    out = open(args.out, "a")
    for repo in sorted(Path(args.repos).iterdir()):
        if not (repo / ".truth.json").is_file():
            continue
        truth = json.loads((repo / ".truth.json").read_text())
        prompt = truth["task"] + f"\n\nThe tests are `{' && '.join(truth['acceptance'])}`."
        for mode in args.modes.split(","):
            # fresh working copy per mode so a --run never sees another mode's change
            work = Path(args.out).parent / "p2work" / f"{repo.name}-{mode}"
            if work.exists():
                subprocess.run(["rm", "-rf", str(work)])
            work.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "clone", "-q", str(repo), str(work)], check=True)
            (work / ".truth.json").unlink(missing_ok=True)
            out_dir = Path(args.out).parent / "p2out" / f"{repo.name}-{mode}"
            out_dir.mkdir(parents=True, exist_ok=True)
            rec = {"tag": args.tag, "repo": repo.name, "mode": mode, "truth": {k: truth[k] for k in ("target", "task_type")}}
            try:
                if mode == "D":
                    rec.update(mode_d(args.unit_url, args.model, work, prompt, skill, out_dir))
                elif mode == "P":
                    rec.update(mode_p(args.cfg, work, prompt, out_dir))
                elif mode == "J":
                    rec.update(mode_j(args.cfg, work, prompt, out_dir))
            except Exception as exc:
                rec["error"] = f"{type(exc).__name__}: {exc}"[:500]
            em = rec.get("emitted") or []
            rec["target_match"] = any(e.get("target") == truth["target"] for e in em)
            rec["type_match"] = any(e.get("task_type") == truth["task_type"] for e in em)
            if args.run and rec.get("contracts"):
                rec["runs"] = [run_contract(args.cfg, c, work, out_dir) for c in rec["contracts"][:2]]
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(json.dumps({k: rec.get(k) for k in ("repo", "mode", "wall_s", "valid", "emitted", "target_match", "type_match", "error", "refusals")}), flush=True)
            if rec.get("runs"):
                print("   runs:", [(r.get("outcome"), r.get("wall_s")) for r in rec["runs"]], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

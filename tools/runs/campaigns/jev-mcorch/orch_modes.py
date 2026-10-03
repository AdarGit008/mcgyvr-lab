#!/usr/bin/env python3
"""Orchestrator modes D / P / J on small repos, one local unit, under the door.

    orch_modes.py LABEL PORT MODEL REPOS_DIR WORK_DIR [--modes D,P,J] [--run]
                  [--jev-port PORT --jev-model NAME]
    orch_modes.py LABEL 0 claude-opus-5-5 REPOS_DIR WORK_DIR --modes D,P \
                  --api anthropic --api-key-env ANTHROPIC_API_KEY \
                  [--price-in 4 --price-out 20]

  D  direct: a chat completion with skills/mcgyvr/SKILL.md (the contract
     schema) plus the repo's files in context; the reply's ```yaml block is
     validated with `mcgyvr contract`. What the API-tier agent does today.
  P  prose delegate: `mcgyvr delegate PROMPT REPO --output DIR`
     (delegate.proposer_for, the orchestrator role).
  J  typed: delegate.classifier_proposer_for through orchestrator.decompose.
     The CLI does not wire it (cli.py:_delegate calls proposer_for only), so
     this harness does, against the same config. With --jev-port the J role is
     bound to the Jev unit and D/P to the orchestrator unit.

The config is written into WORK_DIR by this harness: fleet.yaml binds `orch`
(and `jev`) to the door's host and the given ports; policy.yaml binds the
ladder, orchestrator and verifier roles, tempdir sandbox, a journal under
WORK_DIR. Each repo under REPOS_DIR is a git checkout holding .truth.json
{task, target, task_type, acceptance}; the prompt is truth.task plus the test
command. Each mode gets a fresh clone, so a --run never sees another mode's
change.

`--api anthropic` is the Ref arm (owner answer 4, 2026-10-03): D posts to the
Anthropic Messages API (raw HTTP; the lab's frozen environment has no SDK) with
the key from --api-key-env, never printed; P binds the config's orchestrator
unit to `https://api.anthropic.com` with `api_key_env`, so `mcgyvr delegate`
reaches the model over the product's own transport (its OpenAI-shaped body on
Anthropic's compatibility endpoint). MODE rows then carry the cost at the
prices given (USD per million tokens).

Rows, tab-separated `host label kind k=v...`:

  MODE   one (repo, mode): emitted, valid, target_match, type_match, wall_s,
         prompt/completion tokens (D only: the server's usage; P/J spend is in
         the journal under WORK_DIR), refused (J), error after `--`
  RUN    one `mcgyvr run` of an emitted contract: outcome, rungs tried, wall_s
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    from mcgyvr.serving import gatelib
except ImportError:
    print(
        "orch_modes: mcgyvr.serving.gatelib will not import — this driver runs "
        "under the door, python -m mcgyvr.serving.run",
        file=sys.stderr,
    )
    sys.exit(2)
gatelib.door_required("orch_modes")
RUN_ID = os.environ.get("RUN_ID", "")
if not RUN_ID:
    print(
        "orch_modes: RUN_ID is unset — this driver is started by the door, "
        "python -m mcgyvr.serving.run, never bare",
        file=sys.stderr,
    )
    sys.exit(2)
H = os.environ.get("RUN_HOST", "")
if not H:
    print(
        "orch_modes: RUN_HOST is unset — the door exports it (gate 5)", file=sys.stderr
    )
    sys.exit(2)

from mcgyvr.config import load as load_config  # noqa: E402
from mcgyvr.delegate import classifier_proposer_for  # noqa: E402
from mcgyvr.orchestrator import attach, build_index, decompose  # noqa: E402
from mcgyvr.pool import source_map  # noqa: E402

REPO = Path(os.environ.get("RUN_ROOT") or Path(__file__).resolve().parents[4])
SKILL = REPO / "product/skills/mcgyvr/SKILL.md"


def tok(value: object) -> str:
    return str(value).replace("\t", " ").replace(" ", "_").replace("\n", " ")


def emit(label: str, kind: str, *fields: str, free: str = "") -> None:
    line = "\t".join([H, label, kind, *fields])
    if free:
        line += "\t-- " + free.replace("\t", " ").replace("\n", " ")[:900]
    print(line, flush=True)


def write_config(
    work: Path,
    port: int,
    model: str,
    jev_port: int | None,
    jev_model: str,
    api: str = "",
    key_env: str = "",
) -> Path:
    cfg = work / "cfg"
    cfg.mkdir(parents=True, exist_ok=True)
    units: dict[str, dict[str, Any]] = {
        "orch": {
            "address": f"http://{H}:{port}",
            "engine": "llama.cpp",
            "model": model,
            "width": 1,
            "window": 32768,
            "output_tokens": 4096,
            "request_timeout_s": 1800,
        }
    }
    if api == "anthropic":
        units["orch"] = {
            "address": "https://api.anthropic.com",
            "model": model,
            "api_key_env": key_env,
            "width": 4,
            "window": 200000,
            "output_tokens": 16000,
            "request_timeout_s": 1800,
        }
    if jev_port is not None:
        units["jev"] = {
            "address": f"http://{H}:{jev_port}",
            "engine": "llama.cpp",
            "model": jev_model,
            "width": 1,
            "window": 16384,
            "output_tokens": 16,
            "request_timeout_s": 600,
        }
    fleet = {"profile": "dev", "units": units}
    policy: dict[str, Any] = {
        "use_case": "coding",
        "deployment": "local-only",
        "ladder": ["orch"],
        "fanout": "none",
        # pool.py binds the orchestrator role only with `model` spelled
        "orchestrator": {"unit": "orch", "model": model},
        "verifier": {
            "unit": "jev" if jev_port is not None else "orch",
            "model": jev_model if jev_port is not None else model,
        },
        "sandbox": {"mode": "tempdir"},
        "journal": {"dir": str(work / "journal")},
    }
    import yaml

    (cfg / "fleet.yaml").write_text(yaml.safe_dump(fleet, sort_keys=False))
    (cfg / "policy.yaml").write_text(yaml.safe_dump(policy, sort_keys=False))
    return cfg


def mcgyvr(args: list[str], cfg: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["MCGYVR_CONFIG"] = str(cfg)
    return subprocess.run(
        [sys.executable, "-m", "mcgyvr.cli", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=3600,
    )


def repo_listing(repo: Path) -> str:
    parts = []
    for p in sorted(repo.rglob("*")):
        if ".git" in p.parts or p.name == ".truth.json" or not p.is_file():
            continue
        parts.append(
            f"### {p.relative_to(repo)}\n```\n{p.read_text(errors='replace')}\n```"
        )
    return "\n\n".join(parts)


def api_post(body: dict[str, Any], key_env: str) -> tuple[dict[str, Any], float]:
    key = os.environ.get(key_env, "")
    if not key:
        raise RuntimeError(f"{key_env} is not set; the Ref arm has no credential")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "server-side-fallback-2026-07-01",
        },
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=1800) as resp:
            doc = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"Messages API HTTP {exc.code}: {detail}") from None
    return doc, time.perf_counter() - t0


def mode_d(
    url: str,
    model: str,
    repo: Path,
    prompt: str,
    out: Path,
    cfg: Path,
    api: str = "",
    key_env: str = "",
) -> dict[str, Any]:
    system = (
        "You are the mcgyvr orchestrator. Author exactly ONE task contract as "
        "YAML for the request, following the schema below. Reply with a single "
        "```yaml block and nothing else. The contract must set task_type, id, "
        "task, target, scope.allow, stop_conditions, acceptance (the repo's test "
        "command if there is one) and limits.max_output_tokens.\n\n"
        + SKILL.read_text(encoding="utf-8")
    )
    user = (
        f"REPOSITORY FILES:\n\n{repo_listing(repo)}\n\nREQUEST:\n{prompt}"
        "\n\nWrite the contract."
    )
    if api == "anthropic":
        doc, wall = api_post(
            {
                "model": model,
                "max_tokens": 16000,
                "system": system,
                "fallbacks": "default",
                "messages": [{"role": "user", "content": user}],
            },
            key_env,
        )
        text = "".join(
            b.get("text", "")
            for b in doc.get("content") or []
            if b.get("type") == "text"
        )
        usage = {
            "prompt_tokens": (doc.get("usage") or {}).get("input_tokens"),
            "completion_tokens": (doc.get("usage") or {}).get("output_tokens"),
        }
    else:
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.0,
            "max_tokens": 2048,
            "stream": False,
        }
        req = urllib.request.Request(
            url + "/v1/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=3600) as resp:
            doc = json.loads(resp.read())
        wall = time.perf_counter() - t0
        text = doc["choices"][0]["message"].get("content") or ""
        usage = doc.get("usage") or {}
    m = re.search(r"```(?:yaml|yml)?\s*\n(.*?)```", text, re.S)
    path = out / "D-contract.yaml"
    path.write_text(m.group(1) if m else text)
    v = mcgyvr(["contract", str(path)], cfg)
    rec: dict[str, Any] = {
        "wall_s": wall,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "valid": v.returncode == 0,
        "contracts": [str(path)] if v.returncode == 0 else [],
        "emitted": [],
        "error": "" if v.returncode == 0 else (v.stderr or v.stdout)[-300:],
    }
    if v.returncode == 0:
        import yaml

        c = yaml.safe_load(path.read_text())
        rec["emitted"] = [{"task_type": c.get("task_type"), "target": c.get("target")}]
    return rec


def mode_p(cfg: Path, repo: Path, prompt: str, out: Path) -> dict[str, Any]:
    d = out / "P"
    d.mkdir(exist_ok=True)
    t0 = time.perf_counter()
    r = mcgyvr(["delegate", prompt, str(repo), "--output", str(d)], cfg)
    wall = time.perf_counter() - t0
    files = sorted(d.glob("*.json"))
    emitted = []
    for f in files:
        c = json.loads(f.read_text())
        emitted.append({"task_type": c.get("task_type"), "target": c.get("target")})
    return {
        "wall_s": wall,
        "valid": bool(files),
        "contracts": [str(f) for f in files],
        "emitted": emitted,
        "error": "" if files else r.stderr[-300:],
    }


def mode_j(cfg: Path, repo: Path, prompt: str, out: Path) -> dict[str, Any]:
    config = load_config(cfg)
    propose = classifier_proposer_for(source_map(config))
    if propose is None:
        raise RuntimeError("the config binds no orchestrator role")
    d = out / "J"
    d.mkdir(exist_ok=True)
    t0 = time.perf_counter()
    with attach(str(repo)) as r:
        index = build_index(r.root)
        dec = decompose(index, prompt, propose=propose, config=config)
    wall = time.perf_counter() - t0
    files, emitted = [], []
    for contract, document in zip(dec.contracts, dec.documents, strict=True):
        p = d / f"{contract.id}.json"
        p.write_text(json.dumps(document, indent=2))
        files.append(str(p))
        emitted.append({"task_type": contract.task_type, "target": contract.target})
    return {
        "wall_s": wall,
        "valid": bool(files),
        "contracts": files,
        "emitted": emitted,
        "refused": not files,
        "error": "" if files else "; ".join(str(x) for x in dec.refusals)[:300],
    }


def run_contract(cfg: Path, contract: str, repo: Path, out: Path) -> dict[str, Any]:
    result = out / (Path(contract).stem + ".result.json")
    t0 = time.perf_counter()
    r = mcgyvr(
        [
            "run",
            contract,
            "--repo",
            str(repo),
            "--sandbox",
            "tempdir",
            "--orchestrator",
            RUN_ID,
            "--result",
            str(result),
        ],
        cfg,
    )
    rec: dict[str, Any] = {"wall_s": time.perf_counter() - t0, "rc": r.returncode}
    if result.is_file():
        doc = json.loads(result.read_text())
        rec["outcome"] = doc.get("outcome")
        rec["rungs"] = ",".join(
            f"{a.get('rung')}:{a.get('verdict')}" for a in doc.get("attempts", [])
        )
    else:
        rec["outcome"] = "no_result"
        rec["err"] = r.stderr[-300:]
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("port", type=int)
    ap.add_argument("model")
    ap.add_argument("repos")
    ap.add_argument("work")
    ap.add_argument("--modes", default="D,P,J")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--jev-port", type=int, default=None)
    ap.add_argument("--jev-model", default="jev")
    ap.add_argument("--api", default="", help="anthropic: the Ref arm")
    ap.add_argument("--api-key-env", default="ANTHROPIC_API_KEY")
    ap.add_argument("--price-in", type=float, default=0.0)
    ap.add_argument("--price-out", type=float, default=0.0)
    ap.add_argument(
        "--write-config-only",
        action="store_true",
        help="write WORK_DIR/cfg for another driver (6-tool-loop.sh) and stop",
    )
    args = ap.parse_args()
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    cfg = write_config(
        work,
        args.port,
        args.model,
        args.jev_port,
        args.jev_model,
        args.api,
        args.api_key_env,
    )
    if args.write_config_only:
        print(cfg)
        return 0
    url = f"http://{H}:{args.port}"
    for repo in sorted(Path(args.repos).iterdir()):
        truth_file = repo / ".truth.json"
        if not truth_file.is_file():
            continue
        truth = json.loads(truth_file.read_text())
        acceptance = " && ".join(truth["acceptance"])
        demonstration = " && ".join(truth.get("demonstration") or [])
        prompt = (
            truth["task"]
            + f"\n\nAcceptance (passes now, must keep passing): `{acceptance}`."
            + f"\nDemonstration (fails now, must pass after): `{demonstration}`."
        )
        for mode in args.modes.split(","):
            clone = work / "repos" / f"{repo.name}-{mode}"
            if clone.exists():
                shutil.rmtree(clone)
            clone.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "clone", "-q", str(repo), str(clone)], check=True)
            (clone / ".truth.json").unlink(missing_ok=True)
            out = work / "out" / f"{repo.name}-{mode}"
            out.mkdir(parents=True, exist_ok=True)
            label = f"{args.label}-{mode}"
            try:
                if mode == "D":
                    rec = mode_d(
                        url,
                        args.model,
                        clone,
                        prompt,
                        out,
                        cfg,
                        args.api,
                        args.api_key_env,
                    )
                elif mode == "P":
                    rec = mode_p(cfg, clone, prompt, out)
                elif mode == "J":
                    rec = mode_j(cfg, clone, prompt, out)
                else:
                    raise ValueError(f"mode {mode!r} is not D, P or J")
            except Exception as exc:
                emit(
                    label,
                    "MODE",
                    f"repo={tok(repo.name)}",
                    "valid=0",
                    free=f"{type(exc).__name__}: {exc}",
                )
                continue
            em = rec.get("emitted") or []
            cost = (rec.get("prompt_tokens") or 0) * args.price_in / 1e6
            cost += (rec.get("completion_tokens") or 0) * args.price_out / 1e6
            t_hit = any(e.get("target") == truth["target"] for e in em)
            k_hit = any(e.get("task_type") == truth["task_type"] for e in em)
            emit(
                label,
                "MODE",
                f"repo={tok(repo.name)}",
                f"emitted={len(em)}",
                f"valid={int(bool(rec.get('valid')))}",
                f"target_match={int(t_hit)}",
                f"type_match={int(k_hit)}",
                f"wall_s={rec['wall_s']:.2f}",
                f"prompt_tokens={rec.get('prompt_tokens', 'na')}",
                f"completion_tokens={rec.get('completion_tokens', 'na')}",
                f"refused={int(bool(rec.get('refused')))}",
                f"cost_usd={cost:.4f}",
                free=rec.get("error", ""),
            )
            if args.run:
                for c in rec.get("contracts", [])[:2]:
                    rr = run_contract(cfg, c, clone, out)
                    emit(
                        label,
                        "RUN",
                        f"repo={tok(repo.name)}",
                        f"contract={tok(Path(c).name)}",
                        f"outcome={tok(rr.get('outcome'))}",
                        f"rungs={tok(rr.get('rungs', ''))}",
                        f"wall_s={rr['wall_s']:.1f}",
                        free=rr.get("err", ""),
                    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

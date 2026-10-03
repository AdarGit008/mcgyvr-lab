#!/usr/bin/env python3
"""One Jev candidate over the labelled slice, through the product's primitive.

    jev_slice.py LABEL PORT MODEL SLICE.jsonl [--no-kwargs] [--limit N]

Runs under the door only (door_required, RUN_ID, RUN_HOST). For each slice row
it re-derives the state from records/measurements and tools/bench/tasks, then
calls ``mcgyvr.decision.classify`` — the product's own request body: one
request per question, max_tokens 1, temperature 0, logprobs, top_logprobs
capped at 20 — three times:

  primary    gate/jev.py's JEV_QUESTIONS over the RICH state the owner ruled
             for the rung (2026-10-03): {task, path, added_lines, original,
             change} — the verify.verdict_state shape plus the added lines
  secondary  the same questions over the added-lines-only state the rung
             sends today (gate/jev.py:build_state's shape)
  verdict    verify.py's VERDICT_QUESTION over verdict_state's shape
             (deterministic_gate "not run")

Every call carries ``chat_template_kwargs: {"enable_thinking": false}``, the
body the product will send once the code agent's change lands (owner answer 1,
2026-10-03); the driver injects it at the transport seam
(``mcgyvr.decision._post_json``) so the prompt and the read stay the product's.
``--no-kwargs`` sends the body as the product sends it today (step 0's
comparison arm only).

Rows, tab-separated `host label kind k=v...`:

  ROW      one slice row: id, label; satisfies_p / in_scope_p /
           regression_level on the rich state, the same with suffix _al on
           the added-lines state, verdict_p; wall_s for all seven questions,
           n_added, prompt_tokens as the server reported for the first rich
           question
  ERR      a row the primitive could not read (DecisionError and kin), the
           error text after `--`
  SUMMARY  n, errors, kwargs, acc@0.5 / auroc / brier / ece10 / yes_rate for
           satisfies (rich), satisfies_al (added lines) and verdict, wall
           medians
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

import yaml

try:
    from mcgyvr.serving import gatelib
except ImportError:
    print(
        "jev_slice: mcgyvr.serving.gatelib will not import, so the door cannot be "
        "proved and nothing is sent — this driver runs under the door, "
        "python -m mcgyvr.serving.run, on the interpreter that has mcgyvr",
        file=sys.stderr,
    )
    sys.exit(2)
gatelib.door_required("jev_slice")
RUN_ID = os.environ.get("RUN_ID", "")
if not RUN_ID:
    print(
        "jev_slice: RUN_ID is unset — this driver is started by the door, "
        "python -m mcgyvr.serving.run, never bare",
        file=sys.stderr,
    )
    sys.exit(2)
H = os.environ.get("RUN_HOST", "")
if not H:
    print(
        "jev_slice: RUN_HOST is unset — the door exports it (gate 5)", file=sys.stderr
    )
    sys.exit(2)

from mcgyvr import decision as dec  # noqa: E402
from mcgyvr import runner as _runner  # noqa: E402
from mcgyvr.gate.jev import JEV_QUESTIONS  # noqa: E402
from mcgyvr.pool import Endpoint, Protocol  # noqa: E402
from mcgyvr.verify import VERDICT_KEY, VERDICT_QUESTION  # noqa: E402

REPO = Path(os.environ.get("RUN_ROOT") or Path(__file__).resolve().parents[4])

#: What the product will send on every Jev call (owner answer 1, 2026-10-03).
KWARGS: dict[str, Any] = {"enable_thinking": False}


def install_kwargs() -> None:
    """Add KWARGS to every body decision.classify posts, at its transport seam."""
    original = _runner._post_json

    def post(
        url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float
    ) -> dict[str, Any]:
        return original(
            url, {**payload, "chat_template_kwargs": KWARGS}, headers, timeout
        )

    dec._post_json = post  # type: ignore[attr-defined]


def tok(value: object) -> str:
    return str(value).replace("\t", " ").replace(" ", "_").replace("\n", " ")


def emit(label: str, kind: str, *fields: str, free: str = "") -> None:
    line = "\t".join([H, label, kind, *fields])
    if free:
        line += "\t-- " + free.replace("\t", " ").replace("\n", " ")[:900]
    print(line, flush=True)


def added_lines(original: str, change: str) -> dict[int, str]:
    out: dict[int, str] = {}
    a, b = original.splitlines(), change.splitlines()
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for tag, _i1, _i2, j1, j2 in sm.get_opcodes():
        if tag in ("insert", "replace"):
            for j in range(j1, j2):
                out[j + 1] = b[j]
    return out


def states(r: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract = yaml.safe_load(
        (REPO / "tools/bench/tasks/py" / r["task"] / "contract.yaml").read_text(
            encoding="utf-8"
        )
    )
    cand = (
        REPO
        / "records/measurements"
        / r["run"]
        / "bench-py/candidates"
        / r["task"]
        / f"{r['arm']}-{r['draw']}.txt"
    )
    change = cand.read_text(encoding="utf-8")
    original = contract.get("target_content") or ""
    added = added_lines(original, change)
    # gate/jev.py:build_state's shape (task, path, added_lines sorted by line),
    # built from the records rather than a ChangeSet; tests/ pin the two shapes
    # against each other so a drift there fails before a row is measured.
    state_jev: dict[str, Any] = {
        "task": contract["task"],
        "path": contract["target"],
        "added_lines": [{"line": n, "text": t} for n, t in sorted(added.items())],
    }
    state_verdict = {
        "task_type": contract["task_type"],
        "task": contract["task"],
        "target": contract["target"],
        "interface": contract.get("interface", ""),
        "deterministic_gate": "not run",
        "original": original,
        "change": change,
    }
    # the rich rung state the owner ruled: verdict_state's fields plus the
    # added lines the rung still judges
    state_rich = {
        **state_verdict,
        "path": contract["target"],
        "added_lines": state_jev["added_lines"],
    }
    return state_rich, state_jev, state_verdict


def auroc(scores: list[float], labels: list[int]) -> float | None:
    pos = [s for s, y in zip(scores, labels, strict=True) if y == 1]
    neg = [s for s, y in zip(scores, labels, strict=True) if y == 0]
    if not pos or not neg:
        return None
    wins = sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def ece(scores: list[float], labels: list[int], bins: int = 10) -> float:
    e = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [
            i
            for i, s in enumerate(scores)
            if lo <= s < hi or (b == bins - 1 and s == 1.0)
        ]
        if idx:
            conf = sum(scores[i] for i in idx) / len(idx)
            acc = sum(labels[i] for i in idx) / len(idx)
            e += len(idx) / len(scores) * abs(conf - acc)
    return e


def summary(name: str, scores: list[float], labels: list[int]) -> list[str]:
    n = len(scores)
    if not n:
        return [f"{name}_n=0"]
    acc = (
        sum(1 for s, y in zip(scores, labels, strict=True) if (s >= 0.5) == (y == 1))
        / n
    )
    brier = sum((s - y) ** 2 for s, y in zip(scores, labels, strict=True)) / n
    a = auroc(scores, labels)
    return [
        f"{name}_n={n}",
        f"{name}_acc={acc:.3f}",
        f"{name}_auroc={'na' if a is None else f'{a:.3f}'}",
        f"{name}_brier={brier:.3f}",
        f"{name}_ece10={ece(scores, labels):.3f}",
        f"{name}_yes_rate={sum(1 for s in scores if s >= 0.5) / n:.3f}",
    ]


def prompt_tokens(url: str, model: str, state: Any) -> int | None:
    """The server's own count for the first question's prompt (usage)."""
    name, q = next(iter(JEV_QUESTIONS.items()))
    body = {
        "model": model,
        "messages": [{"role": "user", "content": dec.build_prompt(state, name, q)}],
        "max_tokens": 1,
        "temperature": 0.0,
        "stream": False,
    }
    req = urllib.request.Request(
        url + "/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            doc = json.loads(resp.read())
        value = (doc.get("usage") or {}).get("prompt_tokens")
        return int(value) if isinstance(value, int) else None
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("port", type=int)
    ap.add_argument("model")
    ap.add_argument("slice")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-kwargs", action="store_true", help="the body as sent today")
    args = ap.parse_args()
    if not args.no_kwargs:
        install_kwargs()
    kwargs_tag = "none" if args.no_kwargs else "enable_thinking=false"
    url = f"http://{H}:{args.port}"
    endpoint = Endpoint(
        source=args.label,
        base_url=url,
        protocol=Protocol.OPENAI,
        max_parallel=1,
        credential_env=None,
    )
    rows = [
        json.loads(line)
        for line in Path(args.slice).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows = [r for r in rows if "id" in r]
    if args.limit:
        rows = rows[: args.limit]
    sat: list[float] = []
    sat_al: list[float] = []
    ver: list[float] = []
    lab: list[int] = []
    walls: list[float] = []
    errors = 0
    for r in rows:
        try:
            state_rich, state_jev, state_verdict = states(r)
        except (OSError, KeyError, yaml.YAMLError) as exc:
            emit(
                args.label,
                "ERR",
                f"id={r['id']}",
                free=f"state: {type(exc).__name__}: {exc}",
            )
            errors += 1
            continue
        t0 = time.perf_counter()
        try:
            d1 = dec.classify(
                endpoint, args.model, state_rich, JEV_QUESTIONS, timeout_s=600
            )
            d1al = dec.classify(
                endpoint, args.model, state_jev, JEV_QUESTIONS, timeout_s=600
            )
            d2 = dec.classify(
                endpoint,
                args.model,
                state_verdict,
                {VERDICT_KEY: VERDICT_QUESTION},
                timeout_s=600,
            )
        except Exception as exc:
            emit(
                args.label, "ERR", f"id={r['id']}", free=f"{type(exc).__name__}: {exc}"
            )
            errors += 1
            continue
        wall = time.perf_counter() - t0
        a = d1.answers
        b = d1al.answers
        s = a["satisfies_task"]
        i = a["in_scope"]
        g = a["regression_risk"]
        s2 = b["satisfies_task"]
        i2 = b["in_scope"]
        g2 = b["regression_risk"]
        v = d2.answers[VERDICT_KEY]
        assert isinstance(s, dec.BoolAnswer) and isinstance(i, dec.BoolAnswer)
        assert isinstance(g, dec.ScoreAnswer) and isinstance(v, dec.BoolAnswer)
        assert isinstance(s2, dec.BoolAnswer) and isinstance(i2, dec.BoolAnswer)
        assert isinstance(g2, dec.ScoreAnswer)
        ptok = prompt_tokens(url, args.model, state_rich)
        emit(
            args.label,
            "ROW",
            f"id={r['id']}",
            f"task={tok(r['task'])}",
            f"src_model={tok(r['model'])}",
            f"label={r['label']}",
            f"satisfies_p={s.probability_true:.4f}",
            f"in_scope_p={i.probability_true:.4f}",
            f"regression_level={g.level:.4f}",
            f"satisfies_p_al={s2.probability_true:.4f}",
            f"in_scope_p_al={i2.probability_true:.4f}",
            f"regression_level_al={g2.level:.4f}",
            f"verdict_p={v.probability_true:.4f}",
            f"wall_s={wall:.3f}",
            f"n_added={len(state_jev['added_lines'])}",
            f"prompt_tokens={ptok if ptok is not None else 'unread'}",
        )
        sat.append(s.probability_true)
        sat_al.append(s2.probability_true)
        ver.append(v.probability_true)
        lab.append(int(r["label"]))
        walls.append(wall)
    walls.sort()
    med = f"{walls[len(walls) // 2]:.3f}" if walls else "na"
    p90 = f"{walls[int(len(walls) * 0.9)]:.3f}" if walls else "na"
    emit(
        args.label,
        "SUMMARY",
        f"n={len(rows)}",
        f"errors={errors}",
        f"model={tok(args.model)}",
        f"kwargs={kwargs_tag}",
        f"wall_row_med_s={med}",
        f"wall_row_p90_s={p90}",
        *summary("satisfies", sat, lab),
        *summary("satisfies_al", sat_al, lab),
        *summary("verdict", ver, lab),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

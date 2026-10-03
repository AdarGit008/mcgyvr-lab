#!/usr/bin/env python3
"""Step 0's probe: what an endpoint hands decision.classify, token by token.

    jev_probe.py LABEL PORT MODEL [--kwargs JSON] [--pad N] [--repeat N]

Under the door only. Posts the exact body ``mcgyvr.decision.classify`` posts
(the prompt from ``decision.build_prompt``, max_tokens 1, temperature 0,
logprobs, top_logprobs = min(20, labels)) for one fixed state and four
questions — two Nouls, a Score, a five-way Choice — and files the first
token's full top_logprobs, the label probabilities the primitive reads, its
confidence, the wall, and the server's cached-token count. Then repeats the
first Noul ``--repeat`` times for the warm max_tokens=1 wall. ``--kwargs`` is
a chat_template_kwargs object the product does NOT send; it is filed to show
the template's effect, never as the product's path. ``--pad N`` adds N filler
lines to the state (the prompt-size axis).

Rows, tab-separated `host label kind k=v...`:

  PROBE   one question: q, wall_s, prompt_tokens, cached_tokens, readable
          (1 when every label was read), top (token:logprob pairs, `;`-joined,
          spaces as _), label_probs, confidence, answer; the error after `--`
  WARM    the repeated question: n, wall_min_s, wall_med_s, wall_max_s
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from typing import Any

try:
    from mcgyvr.serving import gatelib
except ImportError:
    print(
        "jev_probe: mcgyvr.serving.gatelib will not import — this driver runs "
        "under the door, python -m mcgyvr.serving.run",
        file=sys.stderr,
    )
    sys.exit(2)
gatelib.door_required("jev_probe")
RUN_ID = os.environ.get("RUN_ID", "")
if not RUN_ID:
    print(
        "jev_probe: RUN_ID is unset — this driver is started by the door, "
        "python -m mcgyvr.serving.run, never bare",
        file=sys.stderr,
    )
    sys.exit(2)
H = os.environ.get("RUN_HOST", "")
if not H:
    print(
        "jev_probe: RUN_HOST is unset — the door exports it (gate 5)", file=sys.stderr
    )
    sys.exit(2)

from mcgyvr import decision as dec  # noqa: E402

STATE: dict[str, Any] = {
    "task": (
        "Add a `retries: int = 3` parameter to fetch_page() in src/pkg/fetch.py "
        "and retry the HTTP GET that many times on a transport error, with the "
        "same timeout each try. Do not touch any other function."
    ),
    "path": "src/pkg/fetch.py",
    "added_lines": [
        {
            "line": 12,
            "text": "def fetch_page(url: str, timeout: float = 5.0, retries: int = 3)"
            " -> str:",
        },
        {"line": 13, "text": "    last: Exception | None = None"},
        {"line": 14, "text": "    for _ in range(retries):"},
        {"line": 15, "text": "        try:"},
        {"line": 16, "text": "            return _get(url, timeout=timeout)"},
        {"line": 17, "text": "        except TransportError as exc:"},
        {"line": 18, "text": "            last = exc"},
        {"line": 19, "text": "    raise RuntimeError('retries exhausted') from last"},
    ],
}

QUESTIONS: dict[str, dec.Question] = {
    "satisfies_task": dec.Noul(
        "Does the added change satisfy the contract's task, as stated?"
    ),
    "in_scope": dec.Noul("Is every added line within the scope the contract allows?"),
    "regression_risk": dec.Score(
        "How likely is the added change to break existing behaviour?",
        levels=("low", "medium", "high"),
    ),
    "kind": dec.Choice(
        "Which task type does this request call for?",
        options={
            "format": "reformat the file, no semantic change",
            "bug_fix": "fix a defect so a failing demonstration passes",
            "function_implementation": "implement a function to a stated interface",
            "docstring": "add or fix docstrings only",
            "rename_symbol": "rename a symbol across the repository",
        },
    ),
}


def tok(value: object) -> str:
    return str(value).replace("\t", " ").replace(" ", "_").replace("\n", "\\n")


def emit(label: str, kind: str, *fields: str, free: str = "") -> None:
    line = "\t".join([H, label, kind, *fields])
    if free:
        line += "\t-- " + free.replace("\t", " ").replace("\n", " ")[:600]
    print(line, flush=True)


def post(url: str, body: dict[str, Any]) -> tuple[dict[str, Any], float]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as resp:
        doc = json.loads(resp.read())
    return doc, time.perf_counter() - t0


def body_for(model: str, prompt: str, labels: int, kwargs: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1,
        "temperature": 0.0,
        "stream": False,
        "logprobs": True,
        "top_logprobs": min(20, labels),
    }
    if kwargs:
        body["chat_template_kwargs"] = json.loads(kwargs)
    return body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("port", type=int)
    ap.add_argument("model")
    ap.add_argument("--kwargs", default="")
    ap.add_argument("--pad", type=int, default=0)
    ap.add_argument("--repeat", type=int, default=5)
    args = ap.parse_args()
    url = f"http://{H}:{args.port}/v1/chat/completions"
    state = dict(STATE)
    if args.pad:
        state["context_files"] = [
            {"line": i, "text": f"# filler {i}: def helper_{i}(x): return x + {i}"}
            for i in range(args.pad)
        ]
    for name, q in QUESTIONS.items():
        prompt = dec.build_prompt(state, name, q)
        labels = dec.labels_for(q)
        doc, wall = post(url, body_for(args.model, prompt, len(labels), args.kwargs))
        usage = doc.get("usage") or {}
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", "na")
        fields = [
            f"q={name}",
            f"wall_s={wall:.4f}",
            f"prompt_tokens={usage.get('prompt_tokens', 'na')}",
            f"cached_tokens={cached}",
            f"pad={args.pad}",
            f"kwargs={tok(args.kwargs) or 'none'}",
        ]
        try:
            top = dec._top_logprobs(doc)
            probs = dec.probabilities_from_logprobs(top, labels)
            answer = dec.answer_for(q, top)
            fields += [
                "readable=1",
                "top="
                + ";".join(
                    f"{tok(e.get('token'))}:{float(e.get('logprob', 0)):.3f}"
                    for e in top
                ),
                "label_probs=" + ",".join(f"{p:.4f}" for p in probs),
                f"confidence={dec.confidence(probs):.4f}",
                f"answer={tok(str(answer)[:120])}",
            ]
            emit(args.label, "PROBE", *fields)
        except dec.DecisionError as exc:
            choice = (doc.get("choices") or [{}])[0]
            content = (choice.get("message") or {}).get("content")
            fields += ["readable=0", f"content={tok(content)}"]
            emit(args.label, "PROBE", *fields, free=str(exc))
    name, q = next(iter(QUESTIONS.items()))
    prompt = dec.build_prompt(state, name, q)
    walls: list[float] = []
    for _ in range(args.repeat):
        _doc, wall = post(url, body_for(args.model, prompt, 2, args.kwargs))
        walls.append(wall)
    walls.sort()
    emit(
        args.label,
        "WARM",
        f"q={name}",
        f"n={len(walls)}",
        f"wall_min_s={walls[0]:.4f}",
        f"wall_med_s={walls[len(walls) // 2]:.4f}",
        f"wall_max_s={walls[-1]:.4f}",
        f"pad={args.pad}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

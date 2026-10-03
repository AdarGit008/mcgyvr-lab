#!/usr/bin/env python3
"""Pilot P0 probe: what a llama.cpp / vLLM endpoint hands `decision.classify`.

Usage: jev_probe.py BASE_URL MODEL TAG [--kwargs '{"enable_thinking": false}']
                    [--repeat N] [--state-chars N]

Posts the exact body `mcgyvr.decision.classify` posts (built with
`decision.build_prompt`), once per question, and prints the FULL top_logprobs
list of the first token, the label probabilities decision.py would read, and
wall time per call. Then repeats the Noul question `--repeat` times to time a
warm max_tokens=1 call (prefix cache on the shared state). Output: one JSON
line per call on stdout; stderr is progress.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request

sys.path.insert(0, "/tmp/claude-1000/-home-adaramir/15b6132f-a502-4a0c-9d7f-4c7b9b894f37/scratchpad/wt/mc-run/src")
from mcgyvr import decision as dec  # noqa: E402

STATE = {
    "task": "Add a `retries: int = 3` parameter to fetch_page() in src/pkg/fetch.py "
    "and retry the HTTP GET that many times on a transport error, with the same "
    "timeout each try. Do not touch any other function.",
    "path": "src/pkg/fetch.py",
    "added_lines": [
        {"line": 12, "text": "def fetch_page(url: str, timeout: float = 5.0, retries: int = 3) -> str:"},
        {"line": 13, "text": "    last: Exception | None = None"},
        {"line": 14, "text": "    for _ in range(retries):"},
        {"line": 15, "text": "        try:"},
        {"line": 16, "text": "            return _get(url, timeout=timeout)"},
        {"line": 17, "text": "        except TransportError as exc:"},
        {"line": 18, "text": "            last = exc"},
        {"line": 19, "text": "    raise RuntimeError('fetch_page: retries exhausted') from last"},
    ],
}

QUESTIONS = {
    "satisfies_task": dec.Noul("Does the added change satisfy the contract's task, as stated?"),
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


def post(url: str, body: dict, timeout: float = 600.0) -> tuple[dict, float]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw), time.perf_counter() - t0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base_url")
    ap.add_argument("model")
    ap.add_argument("tag")
    ap.add_argument("--kwargs", default="", help="chat_template_kwargs JSON")
    ap.add_argument("--repeat", type=int, default=5)
    ap.add_argument("--pad", type=int, default=0, help="pad state with N filler lines")
    args = ap.parse_args()
    url = args.base_url.rstrip("/") + "/v1/chat/completions"
    state = dict(STATE)
    if args.pad:
        state["context_files"] = [
            {"line": i, "text": f"# filler line {i}: def helper_{i}(x): return x + {i}"}
            for i in range(args.pad)
        ]
    for name, q in QUESTIONS.items():
        prompt = dec.build_prompt(state, name, q)
        labels = dec.labels_for(q)
        body = {
            "model": args.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1,
            "temperature": 0.0,
            "stream": False,
            "logprobs": True,
            "top_logprobs": min(20, len(labels)),
        }
        if args.kwargs:
            body["chat_template_kwargs"] = json.loads(args.kwargs)
        doc, dt = post(url, body)
        out = {"tag": args.tag, "q": name, "wall_s": round(dt, 4), "labels": labels}
        try:
            top = dec._top_logprobs(doc)
            out["top"] = [(e.get("token"), round(float(e.get("logprob")), 4)) for e in top]
            probs = dec.probabilities_from_logprobs(top, labels)
            out["label_probs"] = [round(p, 4) for p in probs]
            out["confidence"] = round(dec.confidence(probs), 4)
            ans = dec.answer_for(q, top)
            out["answer"] = str(ans)[:200]
        except Exception as exc:  # DecisionError or shape
            out["error"] = f"{type(exc).__name__}: {exc}"[:300]
            out["raw_choice"] = json.dumps(doc.get("choices", [{}])[0])[:600]
        out["usage"] = doc.get("usage")
        out["content"] = (doc.get("choices") or [{}])[0].get("message", {}).get("content")
        out["reasoning"] = (doc.get("choices") or [{}])[0].get("message", {}).get("reasoning_content")
        print(json.dumps(out), flush=True)
    # warm repeats of the first question: the max_tokens=1 latency with the
    # shared state already in the slot's cache
    q = QUESTIONS["satisfies_task"]
    prompt = dec.build_prompt(state, "satisfies_task", q)
    body = {
        "model": args.model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1,
        "temperature": 0.0,
        "stream": False,
        "logprobs": True,
        "top_logprobs": 2,
    }
    if args.kwargs:
        body["chat_template_kwargs"] = json.loads(args.kwargs)
    times = []
    for _ in range(args.repeat):
        doc, dt = post(url, body)
        times.append(dt)
    times.sort()
    print(
        json.dumps(
            {
                "tag": args.tag,
                "q": "satisfies_task-repeat",
                "n": len(times),
                "wall_min_s": round(times[0], 4),
                "wall_med_s": round(times[len(times) // 2], 4),
                "wall_max_s": round(times[-1], 4),
                "prompt_tokens": (doc.get("usage") or {}).get("prompt_tokens"),
            }
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

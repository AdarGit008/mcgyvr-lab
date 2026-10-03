#!/usr/bin/env python3
"""Step 8: Jev candidates over hand-labelled items (J1/J2/J3, in_scope, risk).

    jev_items.py LABEL PORT MODEL ITEMS.jsonl [--limit N] [--no-kwargs]

Under the door only. Each item is one ``mcgyvr.decision.classify`` call (the
product's body, with the owner's chat_template_kwargs injected as
jev_slice.py does). Rows:

  ITEM     id, question, kind, label, answer (the primitive's peak), p_label
           (probability on the gold answer), confidence, correct, wall_s
  ERR      an item the primitive could not read
  SUMMARY  per question: n, acc, mean p_label, refusal rate at confidence 0.5
           (ClassifierProposer's MIN_CONFIDENCE), errors

THE ITEMS FILE (owner answer 3, 2026-10-03)

Read by `jev_items.py` (step 8). One JSON object per line; the first line is a
`{"_provenance": ...}` header naming the transcripts, the labeller, the date
and the spot-check sample. Every other line:

| key | value |
|---|---|
| `id` | stable, `<question>-<nnn>` |
- `question`:
    `j1_intent` \\
    `j2_ready` \\
    `j3_next` \\
    `in_scope` \\
    `regression_risk`
| `kind` | `choice` \\| `noul` \\| `score` |
| `instructions` | the question text the model reads (fixed per question, below) |
| `options` | choice only: `{key: description}`, fixed per question, below |
| `levels` | score only: `["low", "medium", "high"]` |
| `state` | the JSON state the question is asked over (below) |
| `label` | the gold answer: an option key, `"Yes"`/`"No"`, or a level name |
| `source` | `{transcript, turn}` the item was drawn from |
| `spot_check` | `true` on the owner's 10% sample |

## The five questions

| question | kind | instructions | options / levels | state |
|---|---|---|---|---|
- `j1_intent`:
    choice
    "What does the user's latest message ask the agent to do?"
    `chat`: talk, explain or answer, no change to the repository; `work`: change the
    repository or run a task in it; `status`: report where the current work stands;
    `abort`: stop the current work
    `{request: <the user's original request>, recent: [<the last 2-4 transcript turns,
    abridged>], latest_user_message: <text>}`
- `j2_ready`:
    noul
    "Is this contract ready to run as written — complete, consistent with the request,
    and with an acceptance or demonstration command that can judge it?"
    Yes/No
    `{request, contract_yaml: <the text written>, validator_output: <`mcgyvr contract`
    stdout/stderr if it was run, else ""> }`
- `j3_next`:
    choice
    "Given the last result, what should the agent do next?"
    `done`: the work is accepted or the request is answered; `replan`: change the
    contract or the approach and run again; `ask_user`: a decision the user must make
    is blocking; `abort`: the loop cannot make progress and should stop
    `{request, last_tool_call: {name, arguments}, last_result: <text, abridged>,
    attempts_so_far: N}`
- `in_scope`:
    noul
    gate/jev.py's: "Is every added line within the scope the contract allows?"
    Yes/No
    gate/jev.py's rich state: `{task, path, added_lines, original, change, scope:
    {allow: [...]}}` — `path` is the file the lines were added to
- `regression_risk`:
    score
    gate/jev.py's: "How likely is the added change to break existing behaviour?"
    low/medium/high
    the same rich state

## Where the items come from

The step-6 transcripts (`records/evidence/<date>-jev-
mcorch/work-<tag>/loops/*.transcript.json`
and the Ref arm's `work-ref/loops/*.transcript.json`): each is the messages
list the harness player sent (system, user, assistant with tool_calls, tool
results) for one repo and one rung.

- `j2_ready`: every `write_file` of a `.yaml` contract, paired with the next
  `mcgyvr contract` tool result when there is one. Gold: the validator's
  verdict when it ran (exit 0 → Yes); else the labeller's reading against the
  schema and the request.
- `j3_next`: every tool result that is a `mcgyvr run` result file read, a
  failing test run, or the final plain-text turn. Gold: what a careful
  operator would do next.
- `in_scope`: every `write_file` of a non-contract file, as added lines against
  the file's prior content, with the open contract's `scope.allow` (or the
  task's `target` when no contract was written). Gold: No when the path is
  outside the allow list (e.g. the rung's own `test_*.py`), else Yes.
- `regression_risk`: the same edits. Gold: the labeller's judgment of the diff
  against the stub (low: additive, interface kept; medium: changes a path
  other code may take; high: alters existing behaviour or deletes).
- `j1_intent`: the user's original request (`work`) and, for the other three
  classes, follow-up messages the labeller writes *in the transcript's
  context* at a chosen turn (a status question, a stop, a remark that asks
  for no change). These are authored, not observed — the header says so and
  `source.authored` is true on them.

60 items per question; the classes balanced as far as the transcripts allow
(stated per question in the header). 10% of each question's items drawn at
random (seed in the header) carry `spot_check: true`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from mcgyvr.serving import gatelib
except ImportError:
    print(
        "jev_items: mcgyvr.serving.gatelib will not import — this driver runs "
        "under the door, python -m mcgyvr.serving.run",
        file=sys.stderr,
    )
    sys.exit(2)
gatelib.door_required("jev_items")
RUN_ID = os.environ.get("RUN_ID", "")
if not RUN_ID:
    print("jev_items: RUN_ID is unset — the door starts this driver", file=sys.stderr)
    sys.exit(2)
H = os.environ.get("RUN_HOST", "")
if not H:
    print(
        "jev_items: RUN_HOST is unset — the door exports it (gate 5)", file=sys.stderr
    )
    sys.exit(2)

from mcgyvr import decision as dec  # noqa: E402
from mcgyvr import runner as _runner  # noqa: E402
from mcgyvr.pool import Endpoint, Protocol  # noqa: E402

KWARGS: dict[str, Any] = {"enable_thinking": False}
MIN_CONFIDENCE = 0.5


def install_kwargs() -> None:
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
        line += "\t-- " + free.replace("\t", " ").replace("\n", " ")[:600]
    print(line, flush=True)


def question_of(item: dict[str, Any]) -> dec.Question:
    kind = item["kind"]
    if kind == "noul":
        return dec.Noul(item["instructions"])
    if kind == "score":
        return dec.Score(item["instructions"], levels=tuple(item["levels"]))
    return dec.Choice(item["instructions"], options=dict(item["options"]))


def read(answer: dec.Answer, item: dict[str, Any]) -> tuple[str, float, float]:
    """(peak answer, probability on the gold label, confidence)."""
    gold = str(item["label"])
    if isinstance(answer, dec.BoolAnswer):
        peak = "Yes" if answer.value else "No"
        p = answer.probability_true if gold == "Yes" else 1.0 - answer.probability_true
        return peak, p, answer.confidence
    if isinstance(answer, dec.ScoreAnswer):
        peak = max(answer.probabilities.items(), key=lambda kv: kv[1])[0]
        return peak, answer.probabilities.get(gold, 0.0), answer.confidence
    assert isinstance(answer, dec.ChoiceAnswer)
    return answer.choice, answer.probabilities.get(gold, 0.0), answer.confidence


def confident_acc(rows: list[tuple[bool, float, float]]) -> float:
    kept = [c for c, _, k in rows if k >= MIN_CONFIDENCE]
    return sum(1 for c in kept if c) / len(kept) if kept else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("port", type=int)
    ap.add_argument("model")
    ap.add_argument("items")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-kwargs", action="store_true")
    args = ap.parse_args()
    if not args.no_kwargs:
        install_kwargs()
    endpoint = Endpoint(
        source=args.label,
        base_url=f"http://{H}:{args.port}",
        protocol=Protocol.OPENAI,
        max_parallel=1,
        credential_env=None,
    )
    items = [
        json.loads(line)
        for line in Path(args.items).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith('{"_')
    ]
    if args.limit:
        items = items[: args.limit]
    per: dict[str, list[tuple[bool, float, float]]] = defaultdict(list)
    errors: dict[str, int] = defaultdict(int)
    for item in items:
        q = question_of(item)
        t0 = time.perf_counter()
        try:
            decision = dec.classify(
                endpoint,
                args.model,
                item["state"],
                {item["question"]: q},
                timeout_s=600,
            )
        except Exception as exc:
            errors[item["question"]] += 1
            emit(
                args.label,
                "ERR",
                f"id={tok(item['id'])}",
                f"question={item['question']}",
                free=f"{type(exc).__name__}: {exc}",
            )
            continue
        wall = time.perf_counter() - t0
        peak, p_label, conf = read(decision.answers[item["question"]], item)
        correct = peak == str(item["label"])
        per[item["question"]].append((correct, p_label, conf))
        emit(
            args.label,
            "ITEM",
            f"id={tok(item['id'])}",
            f"question={item['question']}",
            f"kind={item['kind']}",
            f"label={tok(item['label'])}",
            f"answer={tok(peak)}",
            f"p_label={p_label:.4f}",
            f"confidence={conf:.4f}",
            f"correct={int(correct)}",
            f"wall_s={wall:.3f}",
        )
    for question, rows in sorted(per.items()):
        n = len(rows)
        emit(
            args.label,
            "SUMMARY",
            f"question={question}",
            f"n={n}",
            f"errors={errors.get(question, 0)}",
            f"acc={sum(1 for c, _, _ in rows if c) / n:.3f}",
            f"p_label_mean={sum(p for _, p, _ in rows) / n:.3f}",
            f"refuse_rate={sum(1 for _, _, c in rows if c < MIN_CONFIDENCE) / n:.3f}",
            f"acc_when_confident={confident_acc(rows):.3f}",
            f"kwargs={'none' if args.no_kwargs else 'enable_thinking=false'}",
        )
    for question, count in errors.items():
        if question not in per:
            emit(
                args.label, "SUMMARY", f"question={question}", "n=0", f"errors={count}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

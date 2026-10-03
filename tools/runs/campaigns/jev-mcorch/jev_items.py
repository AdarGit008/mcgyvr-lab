#!/usr/bin/env python3
"""Step 8: Jev candidates over hand-labelled items (J1/J2/J3, in_scope, risk).

    jev_items.py LABEL PORT MODEL ITEMS.jsonl [--limit N] [--no-kwargs]

Under the door only. ITEMS.jsonl is the labelled corpus owner answer 3 asked
for (60 items per question, labelled by an Opus subagent from the step-6
transcripts, 10% set aside for the owner's spot check): one JSON object per
line with

    id        a stable id
    question  the question's name: j1_intent | j2_ready | j3_next | in_scope |
              regression_risk
    kind      choice | noul | score
    instructions, and `options` ({key: description}) for a choice or `levels`
    (lowest first) for a score
    state     the JSON state the question is asked over
    label     the gold answer: an option key, "Yes"/"No", or a level name

Each item is one ``mcgyvr.decision.classify`` call (the product's body, with
the owner's chat_template_kwargs injected as jev_slice.py does). Rows:

  ITEM     id, question, kind, label, answer (the primitive's peak), p_label
           (probability on the gold answer), confidence, correct, wall_s
  ERR      an item the primitive could not read
  SUMMARY  per question: n, acc, mean p_label, refusal rate at confidence 0.5
           (ClassifierProposer's MIN_CONFIDENCE), errors
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

# The lab's part of a split test file. The tests of this file that are the
# product's were removed here; they remain in the product's file at this path.
"""A live row names what answered it, what it was asked, and under which round.

``tools/bench/identity.py`` states what a measurement records — four groups,
one block. A journal row that said only ``rung`` and ``model`` could not be laid
beside a bench cell, because it would not say which endpoint served it, which
system prompt it carried or which product revision dispatched it. So each live
row carries the identity fields it can know at dispatch time:

* ``endpoint``, ``model``, ``protocol``, ``condition == "stock"``,
  ``orchestrator``, ``rung``, ``bundle_sha256`` (the system prompt, hashed the
  way ``tools/bundle/measure.py`` hashes it) — always;
* ``round`` and ``product_sha256`` — when the process runs inside this repo
  checkout, read from ``tools/bench/product`` loaded by path the way
  ``tools/breadth/measure.py`` loads it. Off-round is NOT refused for live
  work (the reader flags it), so the digest recorded is the tree's, whether or
  not it matches the open round's pin.

Absent-is-honest applies to the last pair: an install that is not this checkout
has no round to name, and a row that carried ``round: null`` or a made-up id
would read to ``product.declare`` as a run that recorded something.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from mcgyvr.pool import Protocol
from mcgyvr.runner import Completion, StopReason
from mcgyvr.telemetry import fold, observe

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Callable

REPO = Path(__file__).resolve().parent.parent

# ``observe`` called through an untyped alias.
_observe = cast("Callable[..., Any]", observe)

SYSTEM = "You are a careful worker. Answer with one fenced block."
USER = "Set VALUE to 1 in src/pkg/messy.py."
ENDPOINT = "http://localhost:8080"


def _bench_product() -> types.ModuleType:
    """``tools/bench/product.py`` by path, through the slot measure.py uses."""
    cached = sys.modules.get("bench_product")
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(
        "bench_product", REPO / "tools" / "bench" / "product.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _completion() -> Completion:
    return Completion(
        text="```python\nVALUE = 1\n```",
        stop_reason=StopReason.COMPLETE,
        raw_stop_reason="stop",
        model="qwen2.5-coder:7b",
        source="workstation",
        protocol=Protocol.OPENAI,
        max_output_tokens=1024,
        latency_s=0.0,
    )


def _record(sink: Path) -> dict[str, Any]:
    _observe(
        _completion,
        path=sink,
        attempt_id="agent-a:impl:local_qwen-7b:1",
        orchestrator="agent-a",
        rung="local_qwen-7b",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER},
        ],
        endpoint=ENDPOINT,
    )
    (row,) = fold(path=sink)
    return row


def test_inside_the_checkout_the_row_carries_the_round_and_the_product_digest(
    tmp_path: Path,
) -> None:
    product = _bench_product()
    row = _record(tmp_path / "journal" / "agent-a.jsonl")

    assert row["round"] == product.open_round()["id"]
    # The tree's digest, not the round's pin: live work is not refused
    # off-round, so what is recorded is what actually dispatched.
    assert row["product_sha256"] == product.digest(REPO)


def test_a_product_surface_that_cannot_be_read_does_not_stop_the_dispatch(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """A surface entry moved without being re-declared makes ``digest`` raise.

    Off-round is recorded, not refused: the attempt still runs, its answer comes
    back, and its one row says the revision could not be read instead of naming
    one.
    """
    from mcgyvr import telemetry

    product = _bench_product()

    def unreadable(_root: Path) -> str:
        raise product.ProductError("src/mcgyvr/moved.py is not a file or a directory")

    monkeypatch.setattr(product, "digest", unreadable)
    telemetry._product_revision.cache_clear()
    ran: list[bool] = []

    def attempt() -> Completion:
        ran.append(True)
        return _completion()

    sink = tmp_path / "journal" / "agent-a.jsonl"
    try:
        answer = _observe(
            attempt,
            path=sink,
            attempt_id="agent-a:impl:local_qwen-7b:1",
            orchestrator="agent-a",
            rung="local_qwen-7b",
            endpoint=ENDPOINT,
        )
    finally:
        telemetry._product_revision.cache_clear()

    assert ran == [True]
    assert answer.text == _completion().text
    (row,) = fold(path=sink)
    assert row["ok"] is True
    assert "round" not in row
    assert "product_sha256" not in row
    assert row["revision_error"] == "ProductError"

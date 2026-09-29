# The lab's part of a split test file. The tests of this file that are the
# product's were removed here; they remain in the product's file at this path.
"""A live prefill is judged by its own measured class tolerance, not decode's.

The owner's ruling (``mcgyvr-lab/records/plans/fleet-identity.md`` §12):
"Prefill tolerance — ruled 8%". A probe's prefill is judged by the prefill class
percent, never the warm decode class percent (``engine.warm_decode_class_pct``):
an on-rig ``read --probe srv2_3b`` prefill a few percent under its lock is inside
vLLM's prefill class and outside vLLM decode's 1%.

The prefill classes are those of
``mcgyvr-lab/records/measurements/fleet-identity-prefill-2026-09-12/README.md``,
recorded in the lab's ``tools/runs/derived.json`` as
``engine.prefill_class_pct``. :mod:`mcgyvr.derived` does not read that file:
it answers from the user's own ``numbers.yaml`` first, and from the product's
shipped ``data/numbers.json`` second. The test below reads its answer, each
percent from the user's file, which a lab test holds the lab's record in
(``tests/lab_numbers.py``):

* **vLLM 8%**: the 3B's 7.86% worst single-sample shortfall, rounded up, after
  the single restart-tail outlier (the 7B's 9,460 tok/s) is dropped;
* **llama.cpp 1%**: 0.37% worst shortfall, floored to the rule's 1%;
* **CPU experts 1%**: 0.13% worst shortfall, floored to 1%.

Warm decode keeps its own classes (vLLM 1, llama.cpp 1, CPU experts 48). A
unit's class still comes from :func:`mcgyvr.fleet.tolerance.tolerance_class`
alone. Every judge of the two fields applies each its own percent: the probe
(:func:`mcgyvr.fleet.probe._approved` feeding :func:`mcgyvr.fleet.alerts.check`)
and :func:`mcgyvr.fleet.alerts.rejudge`. A row filed from here on carries the
percent its field was judged at.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from tests import lab_numbers

REPO = Path(__file__).resolve().parent.parent
PREFILL_RECORD = (
    REPO
    / "records"
    / "measurements"
    / "fleet-identity-prefill-2026-09-12"
    / "results-prefill.json"
)
#: The 3B's median prefill in that record, whose worst sample sets vLLM's 8%.
THREE_B = "mcgyvr-srv2-Qwen-Qwen2.5-Coder-3B-Instruct-AWQ-8001"
#: The mtp class's prefill tolerance, derived from the mtp-ornith window
#: (owner, 2026-09-16); its warm decode is the same rule over that window.
MTP_RECORD = (
    REPO
    / "records"
    / "measurements"
    / "lock-fleets"
    / "mtp-ornith"
    / "prefill-tolerance-mtp.json"
)


# --- the numbers ------------------------------------------------------------


def test_prefill_and_decode_each_state_their_own_class_percents() -> None:
    measured = json.loads(PREFILL_RECORD.read_text(encoding="utf-8"))
    mtp = json.loads(MTP_RECORD.read_text(encoding="utf-8"))
    tolerances = lab_numbers.class_tolerances()

    assert tolerances["prefill_tok_s"] == {
        "vllm": float(math.ceil(measured["per_unit"][THREE_B]["shortfall_pct"])),
        "llamacpp": float(measured["classes"]["llamacpp"]["tolerance_pct"]),
        "cpu_experts": float(measured["classes"]["cpu_experts"]["tolerance_pct"]),
        "mtp": float(mtp["tolerance_pct"]),
    }
    assert tolerances["prefill_tok_s"] == {
        "vllm": 8.0,
        "llamacpp": 1.0,
        "cpu_experts": 1.0,
        "mtp": 5.0,
    }
    assert tolerances["warm_decode_tok_s"] == {
        "vllm": 1.0,
        "llamacpp": 1.0,
        "cpu_experts": 48.0,
        "mtp": 2.0,
    }

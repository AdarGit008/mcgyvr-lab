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
it answers from the product's shipped ``data/numbers.json``, or from the
user's own ``numbers.yaml`` first, and the test below reads its answer:

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
from typing import Any

import pytest

from tests import test_a_live_probe_is_judged_against_its_lock as probed

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
RUN_ID = "run-20260915T120000-0a1b2c3d"


# --- the numbers ------------------------------------------------------------


def test_prefill_and_decode_each_state_their_own_class_percents() -> None:
    from mcgyvr import derived

    measured = json.loads(PREFILL_RECORD.read_text(encoding="utf-8"))
    mtp = json.loads(MTP_RECORD.read_text(encoding="utf-8"))
    tolerances = derived.class_tolerances()

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


# --- the probe's judge ------------------------------------------------------


def _approved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unit: str) -> Any:
    """The probe's view of ``unit``, from a promoted lock and mcgyvr.derived."""
    from mcgyvr import derived
    from mcgyvr.fleet import probe
    from mcgyvr.fleet.admit import layout_ids

    probed.live_home(tmp_path, monkeypatch)
    fleet = probed.FLEET
    block = fleet["units"][unit]
    rig_id = fleet["rigs"][block["rig"]]["rig_id"]
    combination = layout_ids(fleet, fleet["fleets"]["b-small"]["layout"])[rig_id]
    approved = probe._approved(
        probed.lock_root(tmp_path),
        rig_id,
        combination,
        unit,
        block,
        derived.class_tolerances(),
    )
    stamp = {
        "fleet": "b-small",
        "rig": block["rig"],
        "rig_id": rig_id,
        "combination_id": combination,
        "unit_id": block["unit_id"],
    }
    return approved, stamp


# --- rejudge ----------------------------------------------------------------

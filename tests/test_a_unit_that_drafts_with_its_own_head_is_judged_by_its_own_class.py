# The lab's part of a split test file. The tests of this file that are the
# product's were removed here; they remain in the product's file at this path.
"""A unit that drafts with its own head is judged by its own tolerance class.

Owner ruling, 2026-09-16, after the mtp-ornith window: ``srv2_ornith_mtp`` —
a llama.cpp unit whose launch argv carries ``--spec-type draft-mtp`` — gets a
class of its own, ``mtp``, and is not judged by ``cpu_experts``' numbers. Those
were measured on srv1 offload (48% warm decode, 1% prefill), not this regime:
the unit's own three cold starts spread 1.63% in warm decode and 4.29% in
prefill, so a live probe judged by the class's 1% prefill would have failed a
sample the lock itself accepted.

* :func:`mcgyvr.fleet.tolerance.tolerance_class` puts a llama.cpp unit whose
  argv (or ``flags``) carries ``--spec-type draft-mtp`` in ``mtp``, whether or
  not experts are on the CPU beside it; any other ``--spec-type`` value, and a
  vLLM unit whatever its argv says, are judged as before.
* Every other unit keeps the class it had: the ruling adds a class, it moves
  nobody. Checked on invented units, and on each unit the committed fleet
  declares against its class with the mtp request taken out, so the check
  holds whichever units the fleet carries.
* ``tools/runs/derived.json``, the lab's record, states ``mtp`` in both judged
  fields: prefill at the 5% ``assemble_evidence.py tolerance`` derived from the
  window (``records/measurements/lock-fleets/mtp-ornith/prefill-tolerance-mtp.json``),
  warm decode at the same rule over the same three runs' decode samples
  (``runs.json``: L = the median of the run medians, tol = max(1, ceil(worst
  shortfall %))), which is 2%. The tests below read the class tolerances
  :mod:`mcgyvr.derived` judges with, each from the user's own
  ``numbers.yaml``, which a lab test holds the lab's record in, and never from
  the product's shipped ``data/numbers.json`` (``tests/lab_numbers.py``). An
  absent ``mtp`` is refused by name, as any class is.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any

import yaml

from mcgyvr.fleet.files import load_fleet
from mcgyvr.fleet.tolerance import (
    CLASS_CPU_EXPERTS,
    CLASS_MTP,
    tolerance_class,
)
from tests import lab_numbers
from tests.lockfleets_window import fleet_doc

REPO = Path(__file__).resolve().parent.parent
USE = REPO / "records" / "measurements" / "lock-fleets" / "mtp-ornith"
UNIT = "srv2_ornith_mtp"


def _without_mtp(unit: dict[str, Any]) -> dict[str, Any]:
    """The unit as it would stand had its launch not asked for mtp."""
    launch = unit.get("launch")
    if not isinstance(launch, dict):
        return unit
    kept = dict(launch)
    for key in ("argv", "flags"):
        words = kept.get(key)
        if isinstance(words, list):
            pairs = {
                index
                for index in range(len(words) - 1)
                if words[index : index + 2] == ["--spec-type", "draft-mtp"]
            }
            kept[key] = [
                word
                for index, word in enumerate(words)
                if index not in pairs
                and index - 1 not in pairs
                and word != "--spec-type=draft-mtp"
            ]
    if kept.get("speculative") == "mtp":
        del kept["speculative"]
    return {**unit, "launch": kept}


def committed_units() -> dict[str, Any]:
    text = (REPO / "fleet-setup" / "fleet.yaml").read_text(encoding="utf-8")
    units: dict[str, Any] = load_fleet(text)["units"]
    return units


# --- the class -------------------------------------------------------------


def test_a_setup_unit_that_asks_for_mtp_is_judged_as_mtp_once_read() -> None:
    """A made-up setup, written as a ``fleet.yaml`` is and read back by the
    same loader. Two units ask to draft with their own head: one keeps experts
    on the CPU and one does not. Both are ``mtp``; without the ask the first is
    ``cpu_experts`` and the second is not ``mtp``; no other unit is ``mtp``."""
    fleet = fleet_doc()
    on_cpu, on_card = "a_solo", "a_pair"
    fleet["units"][on_cpu]["launch"]["argv"] += ["--n-cpu-moe", "4"]
    for name in (on_cpu, on_card):
        fleet["units"][name]["launch"]["argv"] += ["--spec-type", "draft-mtp"]
    units = load_fleet(yaml.safe_dump(fleet, sort_keys=False))["units"]
    for name in (on_cpu, on_card):
        assert "--spec-type" in units[name]["launch"]["argv"], name
        assert tolerance_class(units[name]) == CLASS_MTP, name
    assert tolerance_class(_without_mtp(units[on_cpu])) == CLASS_CPU_EXPERTS
    assert tolerance_class(_without_mtp(units[on_card])) != CLASS_MTP
    for name, unit in units.items():
        if name not in (on_cpu, on_card):
            assert tolerance_class(unit) != CLASS_MTP, name


def test_each_declared_unit_is_mtp_only_where_it_asks_and_else_as_before() -> None:
    for name, unit in committed_units().items():
        before = tolerance_class(_without_mtp(unit))
        assert before != CLASS_MTP, name
        if _without_mtp(unit) == unit:
            assert tolerance_class(unit) == before, name
        else:
            assert tolerance_class(unit) == CLASS_MTP, name


# --- the numbers ----------------------------------------------------------------


def _derived() -> dict[str, dict[str, float]]:
    """The class tolerances judged with: the lab's record, from the user's file."""
    return lab_numbers.class_tolerances()


def test_mtp_prefill_is_the_tolerance_the_window_derived() -> None:
    doc = json.loads((USE / "prefill-tolerance-mtp.json").read_text(encoding="utf-8"))
    assert doc["unit"] == UNIT and doc["class"] == CLASS_MTP
    assert doc["tolerance_pct"] == 5
    assert _derived()["prefill_tok_s"][CLASS_MTP] == 5.0


def test_mtp_warm_decode_is_the_same_rule_over_the_same_three_runs() -> None:
    runs = json.loads((USE / "runs.json").read_text(encoding="utf-8"))["runs"]
    figures = [
        run["figures"][UNIT]
        for run in runs.values()
        if run["kind"] == "unit" and run["units"] == [UNIT] and "retried_by" not in run
    ]
    assert len(figures) == 3
    locked = statistics.median([f["warm_decode_tok_s"] for f in figures])
    samples = [s for f in figures for s in f["decode_samples"]]
    assert len(samples) == 15
    worst = max(max(0.0, (locked - s) / locked * 100.0) for s in samples)
    assert 1.0 < worst < 2.0
    assert _derived()["warm_decode_tok_s"][CLASS_MTP] == float(max(1, math.ceil(worst)))
    assert _derived()["warm_decode_tok_s"][CLASS_MTP] == 2.0


def test_the_other_classes_numbers_did_not_move() -> None:
    tolerances = _derived()
    decode = {
        k: v for k, v in tolerances["warm_decode_tok_s"].items() if k != CLASS_MTP
    }
    prefill = {k: v for k, v in tolerances["prefill_tok_s"].items() if k != CLASS_MTP}
    assert decode == {"vllm": 1.0, "llamacpp": 1.0, "cpu_experts": 48.0}
    assert prefill == {"vllm": 8.0, "llamacpp": 1.0, "cpu_experts": 1.0}

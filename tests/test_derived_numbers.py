# The lab's part of a split test file. The tests of this file that are the
# product's were removed here; they remain in the product's file at this path.
"""The lab's per-rig derived-numbers record.

``tools/runs/derived.json`` is the lab's record of the numeric values it
measured on its rigs rather than read from the rig or from the model: the
runtime-resident intercept host-RAM sizing adds to spilled experts, the
per-rig card remainder ``vramfit``'s ``C`` subsumes, and the class tolerances
the fleet lock weighs NVMe against and a live probe is judged by.

:mod:`mcgyvr.derived` does not read this file. The product answers from its
own shipped estimates (``data/numbers.json``), keyed by a tolerance class or
an engine and never by a machine's name, and a user's own ``numbers.yaml``
answers first. A test here that calls :mod:`mcgyvr.derived` judges with the
product's estimates.

This file holds the record to the same contract ``test_declared_host_state.py``
holds ``tools/runs/hosts.json`` to: every number states a value and why it is
that value. How :mod:`mcgyvr.derived` resolves and refuses a number is
tested in the product, for example
``product/tests/test_a_number_nobody_stated_is_refused_by_name.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mcgyvr import derived

REPO = Path(__file__).resolve().parent.parent
DERIVED = REPO / "tools" / "runs" / "derived.json"


def document() -> dict[str, Any]:
    loaded = json.loads(DERIVED.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "the derived-numbers file is not a JSON object"
    return loaded


def _unexplained(numbers: dict[str, Any]) -> list[str]:
    """Which entries state no value or no reason, mirroring the host-state check."""
    return sorted(
        name
        for name, body in numbers.items()
        if not name.startswith("_")
        and (
            not isinstance(body, dict)
            or not str(body.get("value", "")).strip()
            or not str(body.get("why", "")).strip()
        )
    )


def test_every_host_names_its_derived_numbers() -> None:
    doc = document()
    assert set(doc["hosts"]) == {"srv1", "srv2"}
    for host in doc["hosts"]:
        assert isinstance(doc[host], dict), host
        assert isinstance(doc[host].get("numbers"), dict), host


def test_every_number_states_a_value_and_why_it_is_that_value() -> None:
    doc = document()
    for host in doc["hosts"]:
        unexplained = _unexplained(doc[host]["numbers"])
        assert not unexplained, (
            f"{host} carries derived numbers without a value or a reason: {unexplained}"
        )
    for entry in ("warm_decode_class_pct", "prefill_class_pct"):
        unexplained = _unexplained(doc["engine"][entry])
        assert not unexplained, (
            f"{entry} class tolerances without a value or a reason: {unexplained}"
        )


def test_the_runtime_resident_intercept_resolves_for_each_rig() -> None:
    assert derived.runtime_resident_gb("srv1") == pytest.approx(1.53)
    assert derived.runtime_resident_gb("srv2") == pytest.approx(1.53)


def test_the_per_rig_card_remainder_is_recorded() -> None:
    doc = document()
    assert doc["srv1"]["numbers"]["card_remainder_mib"]["value"] == 97.69
    assert doc["srv2"]["numbers"]["card_remainder_mib"]["value"] == 144.67

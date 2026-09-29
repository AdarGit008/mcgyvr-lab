"""The lab's measured numbers, handed to the product as a user's own.

``tools/runs/derived.json`` is the lab's record of the numbers it measured on
its rigs. The product reads no file under ``tools/``: :mod:`mcgyvr.derived`
answers from the user's own ``numbers.yaml`` first and from the product's
shipped estimates second. So the lab writes its record into that file
(:func:`write`, in each test's HOME, from ``tests/conftest.py``), and a lab
test that judges a unit judges with the lab's own numbers, each checked to
come from the user's file and to equal the record
(:func:`class_tolerances`). A product default may then change without a lab
measurement first, and no lab test fails when it does.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from mcgyvr import derived

REPO = Path(__file__).resolve().parent.parent
#: The lab's record of the numbers it measured on its rigs.
RECORD = REPO / "tools" / "runs" / "derived.json"


def record() -> dict[str, Any]:
    """The lab's record, as its JSON states it."""
    loaded = json.loads(RECORD.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{RECORD} is not a JSON object"
    return loaded


def _by_class(doc: dict[str, Any], entry: str) -> dict[str, float]:
    """``entry``'s value per tolerance class, from the record's ``engine`` block."""
    return {
        name: float(body["value"])
        for name, body in doc["engine"][entry].items()
        if not name.startswith("_")
    }


def recorded_percents(field: str) -> dict[str, float]:
    """``field``'s percent per tolerance class, as the lab's record states it."""
    return _by_class(record(), derived.CLASS_PCT_ENTRIES[field])


def user_numbers() -> dict[str, dict[str, float]]:
    """The lab's record as the user's ``numbers.yaml`` states it: name -> key -> value.

    * ``engine.warm_decode_class_pct`` and ``engine.prefill_class_pct`` are
      keyed by tolerance class in the record and in the product alike, and
      are written as they are.
    * ``runtime_resident_gb`` is recorded per rig, measured on llama.cpp on
      each; the product keys it by engine, so it is written once, under
      ``llama.cpp``. Every rig must record the same value: rigs that differ
      are refused, so no rig's value silently stands for the others.
    * ``card_remainder_mib`` is left out: the product ships no such number,
      and it refuses a user's file that sets a number it does not ship.
    """
    doc = record()
    stated = {
        entry: _by_class(doc, entry) for entry in derived.CLASS_PCT_ENTRIES.values()
    }
    per_rig = {
        rig: float(doc[rig]["numbers"][derived.RUNTIME_RESIDENT]["value"])
        for rig in doc["hosts"]
    }
    values = set(per_rig.values())
    assert len(values) == 1, (
        f"{RECORD} records {derived.RUNTIME_RESIDENT} per rig as {per_rig}; the "
        f"product keys it by engine ({derived.RUNTIME_RESIDENT_KEY}), so the rigs "
        "must agree"
    )
    stated[derived.RUNTIME_RESIDENT] = {derived.RUNTIME_RESIDENT_KEY: values.pop()}
    return stated


def write() -> Path:
    """Write the lab's numbers where the product reads the user's own; say where.

    The place is the product's to say (:func:`mcgyvr.derived.overrides_path`,
    ``numbers.yaml`` in mcgyvr's own folder under the current HOME), so this
    writes a file and patches nothing of the product's.
    """
    where = derived.overrides_path()
    where.parent.mkdir(parents=True, exist_ok=True)
    where.write_text(yaml.safe_dump(user_numbers()), encoding="utf-8")
    return where


def class_tolerances() -> dict[str, dict[str, float]]:
    """Judged field -> class -> the percent :mod:`mcgyvr.derived` judges with.

    Every percent is checked to come from the user's own file (source
    ``override``), not from the product's shipped estimate, and to equal the
    lab's record; one failure names every percent that does not.
    """
    answered = derived.class_tolerance_numbers()
    not_ours = {
        f"{field}[{name!r}]": f"the {number.source} in {number.where}"
        for field, by_class in answered.items()
        for name, number in by_class.items()
        if number.source != "override"
    }
    assert not not_ours, (
        f"{', '.join(sorted(not_ours))} are not the lab's own, from the user's "
        f"file; each came from {' or '.join(sorted(set(not_ours.values())))}"
    )
    percents = {
        field: {name: number.value for name, number in by_class.items()}
        for field, by_class in answered.items()
    }
    assert percents == {field: recorded_percents(field) for field in percents}, (
        f"the percents judged with are not the ones {RECORD} records"
    )
    return percents

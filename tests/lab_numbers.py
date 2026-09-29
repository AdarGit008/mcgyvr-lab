"""The lab's measured numbers, and the check that a lab test judges with them.

``tools/runs/derived.json`` is the lab's record of the numbers it measured on
its rigs. The product reads no file under ``tools/``: :mod:`mcgyvr.derived`
answers from the user's own ``numbers.yaml`` first and from the product's
shipped estimates second. A lab test that judges a unit judges with the lab's
own numbers, so each number it judges with must come from the user's file and
equal this record. A product default may then change without a lab
measurement first, and no lab test fails when it does.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcgyvr import derived

REPO = Path(__file__).resolve().parent.parent
#: The lab's record of the numbers it measured on its rigs.
RECORD = REPO / "tools" / "runs" / "derived.json"


def record() -> dict[str, Any]:
    """The lab's record, as its JSON states it."""
    loaded = json.loads(RECORD.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{RECORD} is not a JSON object"
    return loaded


def recorded_percents(field: str) -> dict[str, float]:
    """``field``'s percent per tolerance class, as the lab's record states it."""
    entry = record()["engine"][derived.CLASS_PCT_ENTRIES[field]]
    return {
        name: float(body["value"])
        for name, body in entry.items()
        if not name.startswith("_")
    }


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

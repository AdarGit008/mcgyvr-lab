# The lab's part of a split test file. The tests of this file that are the
# product's were removed here; they remain in the product's file at this path.
"""A fleet.yaml the lock accepts is a fleet.yaml a run can read.

``mcgyvr fleet lock`` requires every unit to carry its ``unit_id``, and
``mcgyvr.fleet.files`` accepts it. ``mcgyvr.config`` validates the same file
again for ``run``, ``pool``, ``emit`` and ``serve``; if it refused
``unit_id``, every locked setup would be unreadable by the commands that serve
it.
"""

from __future__ import annotations

from pathlib import Path

from mcgyvr import config

REPO = Path(__file__).resolve().parent.parent


def test_the_stamped_dev_setup_loads_as_the_run_config() -> None:
    fleet = (REPO / "fleet-setup" / "fleet.yaml").read_text(encoding="utf-8")
    policy = (REPO / "fleet-setup" / "policy.yaml").read_text(encoding="utf-8")
    loaded = config.parse(fleet, policy)
    assert set(loaded.ladder.names) <= set(loaded.units)

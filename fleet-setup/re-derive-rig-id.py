#!/usr/bin/env python3
"""Re-derive one rig's id from a fresh door-read snapshot, and print the fields.

Since the card-slot change (product PR #550, merged as ``4214aea7``),
``mcgyvr.fleet.ids.rig_id`` hashes each card's PCI slot (``gpu_slot`` for device
0, and ``gpu_others`` for the cards beyond device 0), so a rig id read under
that spelling differs from every id pinned before it. This script turns one
snapshot — the ``k=v`` lines ``rig-snapshot.sh`` prints, as carried by the door
read's ``snapshot`` field — into the new id and the exact fields it hashes.

It writes nothing. It is a check: its ``rig_id`` must equal the read's
``observed_rig_id``.

Run from the lab root, after a read-only door read of the rig::

    python -m mcgyvr.serving.run read --host srv1
    # take the read's `snapshot` field, as `k=v` lines, then:
    uv run --no-sync python fleet-setup/re-derive-rig-id.py srv1 < snapshot.txt

Output:

* the derived ``rig_id``;
* the ``fields`` tree ``rig_id`` hashes — ``host``, ``hardware`` and
  ``system`` — in the exact tokenized strings, so it can be pasted into the
  ``rig`` block of ``fleet-setup/digests-<rig>.json``;
* the ``rigs.<rig>.rig_id`` line for ``fleet-setup/fleet.yaml``.
"""

from __future__ import annotations

import json
import sys

from mcgyvr.fleet.ids import RIG_EXTRA_CARDS, RIG_HARDWARE, RIG_SYSTEM, rig_id


def load_snapshot(lines: list[str]) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        snapshot[key.strip()] = value.strip()
    return snapshot


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "?"
    snapshot = load_snapshot(sys.stdin.read().splitlines())
    try:
        rid = rig_id(snapshot)
    except ValueError as err:
        print(f"refused: {err}", file=sys.stderr)
        return 1

    hardware = {key: snapshot[key] for key in RIG_HARDWARE}
    extras = snapshot.get(RIG_EXTRA_CARDS, "").strip()
    if extras:
        hardware[RIG_EXTRA_CARDS] = extras

    rig_block = {
        "name": name,
        "rig_id": rid,
        "fields": {
            "host": snapshot["hostname"],
            "hardware": hardware,
            "system": {key: snapshot[key] for key in RIG_SYSTEM},
        },
    }

    print(f"# {name}: rig_id")
    print(rid)
    print()
    print(f"# fleet-setup/digests-{name}.json -> rig")
    print(json.dumps(rig_block, indent=2, sort_keys=True))
    print()
    print(f"# fleet-setup/fleet.yaml -> rigs.{name}.rig_id")
    print(f'    rig_id: "{rid}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The serving harness's markers, checked before a serving campaign's step.

The campaign marker check is the lab's (owner ruling): it checks that the
serving harness on disk is the harness that was edited, which is measuring,
not serving. This is the lab's gate for it, written for a door's caller gate
list in phase ``after``, so it runs once the door has leased and read the
machine and before the step. It exports nothing, and it imports nothing of
the product: it holds whatever gates the product's door keeps.

It reads the run from the environment a door gives its gates: ``RUN_ROOT``,
the tree the run runs from, and ``RUN_CAMPAIGN``. When
``tools/runs/campaigns/<RUN_CAMPAIGN>/campaign.json`` under the root says
``"serving": true``, it loads ``verify_markers`` from the root's
``tools/bench/serving/launch.py`` and runs it over the root; any problem is a
refusal, exit 2, naming the marker. A campaign that does not serve, or has no
``campaign.json``, is not held to the serving markers. A run it cannot name,
or a declaration or harness file it cannot read, is refused and says why.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn

#: Where a campaign's folder sits under the run root.
CAMPAIGNS = Path("tools") / "runs" / "campaigns"
#: The serving harness's marker list and its check, under the run root.
LAUNCH = Path("tools") / "bench" / "serving" / "launch.py"


def refuse(rule: str) -> NoReturn:
    """Say which rule refused, then stop with the door's refusal status."""
    sys.stderr.write(f"{Path(sys.argv[0]).name}: {rule}\n")
    raise SystemExit(2)


def need(key: str) -> str:
    """A variable the door gives its gates. Absent, the run cannot be named."""
    value = os.environ.get(key)
    if not value:
        refuse(
            f"{key} is not set; this gate reads the run from the environment a "
            "door gives its gates"
        )
    return value


def serves(root: Path, campaign: str) -> bool:
    """Whether the campaign's ``campaign.json`` says ``"serving": true``."""
    if campaign in (".", "..") or Path(campaign).name != campaign:
        refuse(f"RUN_CAMPAIGN {campaign!r} is not the name of one campaign folder")
    path = root / CAMPAIGNS / campaign / "campaign.json"
    if not path.is_file():
        return False
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        refuse(f"{path} cannot be read as JSON: {error}")
    if not isinstance(doc, dict):
        refuse(f"{path} is not a JSON object")
    return doc.get("serving") is True


def problems(root: Path) -> list[str]:
    """``verify_markers`` of the root's harness, over the root."""
    path = root / LAUNCH
    if not path.is_file():
        refuse(
            f"{LAUNCH.as_posix()} is not under {root}; a serving campaign's "
            "markers are listed there"
        )
    spec = importlib.util.spec_from_file_location("_serving_launch", path)
    if spec is None or spec.loader is None:
        refuse(f"{path} cannot be loaded as a module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    verify: Callable[[Path], list[str]] = module.verify_markers
    try:
        return verify(root)
    except OSError as error:
        refuse(f"a file the serving markers name cannot be read: {error}")


def main() -> int:
    root = Path(need("RUN_ROOT"))
    campaign = need("RUN_CAMPAIGN")
    if not serves(root, campaign):
        print(f"serving markers: campaign {campaign} does not serve; not checked")
        return 0
    found = problems(root)
    if found:
        refuse("the serving harness on disk fails its own markers: " + "; ".join(found))
    print(f"serving markers: campaign {campaign} serves; its harness holds them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

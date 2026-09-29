"""The serving harness's markers, checked before a serving campaign's step.

The campaign marker check is the lab's (owner ruling): it checks that the
serving harness on disk is the harness that was edited, which is measuring,
not serving. This is the lab's gate for it, written for the gate list a
caller is to hand the door's step verb, in phase ``after``: it runs once the
door has leased and read the machine, and before the step. The product's
door has no step verb yet. Until it has, a campaign reaches the door through
its campaign entry, whose gate 2b runs the same check with the run root's
own harness. The door's ``serve`` and ``read`` give this gate no campaign to
check: ``serve`` names its campaign ``live-<host>``, which has no campaign
folder, and ``read`` names none, which this gate refuses. Which name carries
the campaign to this gate under the step verb is for the verb to settle.

The gate exports nothing and imports nothing of the product, so it works
whichever gates the product's door keeps. For that reason :func:`refuse` and
:func:`need` repeat the product's ``gatelib.refuse`` and ``gatelib.need``
(the same exit status, the same test of a variable, the same form of message)
rather than import them.

It reads the run from the environment a door gives its gates: ``RUN_ROOT``,
the tree the run runs from, and ``RUN_CAMPAIGN``. When
``tools/runs/campaigns/<RUN_CAMPAIGN>/campaign.json`` under the root says
``"serving": true``, it loads ``verify_markers`` from the root's
``tools/bench/serving/launch.py`` and runs it over the root; any problem is a
refusal, exit 2, naming every marker that fails. A campaign with no
``campaign.json``, or whose ``campaign.json`` does not say ``"serving":
true``, is not held to the serving markers, and the gate says which of the
two it found. Refused with exit 2, naming what failed: an unset or empty
``RUN_ROOT`` or ``RUN_CAMPAIGN``; a root that is not a folder; a campaign
name that is not one folder name; a ``campaign.json`` that cannot be read or
is not a JSON object; for a serving campaign, a root with no ``launch.py``, a
``launch.py`` that cannot be read, does not parse or has no
``verify_markers``, and a file its markers name that cannot be read as UTF-8
text.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any, NoReturn

#: Where a campaign's folder sits under the run root.
CAMPAIGNS = Path("tools") / "runs" / "campaigns"
#: The serving harness's marker list and its check, under the run root.
LAUNCH = Path("tools") / "bench" / "serving" / "launch.py"
#: The module name the root's ``launch.py`` is loaded under.
MODULE = "_serving_launch"


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


def run_root() -> Path:
    """``RUN_ROOT``, which must name a folder."""
    root = Path(need("RUN_ROOT"))
    try:
        folder = root.is_dir()
    except OSError as error:
        refuse(f"RUN_ROOT {str(root)!r} cannot be looked at: {error}")
    if not folder:
        refuse(f"RUN_ROOT {str(root)!r} is not a folder")
    return root


def declaration(root: Path, campaign: str) -> dict[str, Any] | None:
    """The campaign's ``campaign.json``, or ``None`` when it has none."""
    if campaign in (".", "..") or Path(campaign).name != campaign:
        refuse(f"RUN_CAMPAIGN {campaign!r} is not the name of one campaign folder")
    path = root / CAMPAIGNS / campaign / "campaign.json"
    try:
        if not path.is_file():
            return None
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        refuse(f"{path} cannot be read as JSON: {error}")
    if not isinstance(doc, dict):
        refuse(f"{path} is not a JSON object")
    return doc


def verifier(root: Path) -> tuple[ModuleType, Callable[[Path], list[str]]]:
    """The root's ``launch.py``, loaded, and its ``verify_markers``."""
    path = root / LAUNCH
    spec = importlib.util.spec_from_file_location(MODULE, path)
    if spec is None or spec.loader is None:
        refuse(f"{path} cannot be loaded as a module")
    module = importlib.util.module_from_spec(spec)
    # Registered before it runs, as an import registers a module: a dataclass
    # in the harness looks its module up by name while it is being defined.
    sys.modules[MODULE] = module
    try:
        if not path.is_file():
            refuse(
                f"{LAUNCH.as_posix()} is not under {root}; a serving campaign's "
                "markers are listed there"
            )
        spec.loader.exec_module(module)
        verify: Callable[[Path], list[str]] = module.verify_markers
    except (OSError, SyntaxError, AttributeError) as error:
        refuse(
            f"{path} cannot be loaded for its verify_markers: "
            f"{type(error).__name__}: {error}"
        )
    return module, verify


def unreadable(root: Path, module: ModuleType) -> list[str]:
    """The files the harness's marker lists name that cannot be read as UTF-8."""
    listed = (*getattr(module, "MARKERS", ()), *getattr(module, "WITHDRAWN", ()))
    found: list[str] = []
    for name in sorted({str(entry[0]) for entry in listed}):
        try:
            (root / name).read_text(encoding="utf-8")
        except (OSError, ValueError):
            found.append(name)
    return found


def problems(root: Path) -> list[str]:
    """``verify_markers`` of the root's harness, over the root."""
    module, verify = verifier(root)
    try:
        return verify(root)
    except (OSError, ValueError) as error:
        named = unreadable(root, module)
        refuse(
            f"a file the serving markers name cannot be read as UTF-8 text under "
            f"{root}"
            + (f": {', '.join(named)}" if named else "")
            + f" ({type(error).__name__}: {error})"
        )


def main() -> int:
    root = run_root()
    campaign = need("RUN_CAMPAIGN")
    doc = declaration(root, campaign)
    if doc is None:
        print(
            f"serving markers: campaign {campaign!r} has no campaign.json; not checked"
        )
        return 0
    if doc.get("serving") is not True:
        print(f"serving markers: campaign {campaign!r} does not serve; not checked")
        return 0
    found = problems(root)
    if found:
        refuse("the serving harness on disk fails its own markers: " + "; ".join(found))
    print(f"serving markers: campaign {campaign!r} serves; its harness holds them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

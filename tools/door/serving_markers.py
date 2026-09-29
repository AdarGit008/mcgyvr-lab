"""The serving harness's markers, checked before a serving campaign's step.

The campaign marker check is the lab's (owner ruling): it checks that the
serving harness on disk is the harness that was edited, which is measuring,
not serving. This is the lab's gate for it, written for the gate list a
caller is to hand the door's step verb, in phase ``after``: it runs once the
door has leased and read the machine, and before the step. The product's
door has no step verb yet. Until it has, a campaign reaches the door through
its campaign entry, whose gate 2b loads ``verify_markers`` from the run
root's harness and runs it over the root, as this gate does. Where the check
cannot be made as asked, this gate refuses, naming what failed, where 2b may
pass or end in a traceback. The door's ``serve`` and ``read`` give this gate
no campaign to check: ``serve`` names its campaign ``live-<host>``, which has
no campaign folder, and ``read`` names none, which this gate refuses. Which
name carries the campaign to this gate under the step verb is for the verb to
settle.

The gate exports nothing. Of the product it uses only the door's library for
its gates, ``gatelib``: ``refuse``, so a refusal has the form and exit status
of the door's own gates, and ``root``, which reads ``RUN_ROOT`` as they do.

It reads the run from the environment a door gives its gates: ``RUN_ROOT``,
the tree the run runs from, and ``RUN_CAMPAIGN``. When
``tools/runs/campaigns/<RUN_CAMPAIGN>/campaign.json`` under the root says
``"serving": true``, it loads ``verify_markers`` from the root's
``tools/bench/serving/launch.py``, with the root first on the import path,
and runs it over the root; any problem is a refusal, exit 2, naming every
marker that fails. A campaign with nothing at the path of its
``campaign.json``, or whose ``campaign.json`` does not say ``"serving":
true``, is not held to the serving markers, and the gate says which of the
two it found. Each of these is refused with exit 2, naming what failed, and
without a traceback: an unset or empty ``RUN_ROOT`` or ``RUN_CAMPAIGN``; a
root that is not a folder or cannot be looked at; a campaign name that is not
one folder name; a ``campaign.json`` that cannot be looked at, is not a file,
cannot be read or is not a JSON object; for a serving campaign, a
``launch.py`` that is not a file or cannot be loaded, a ``verify_markers``
that fails or does not return a list of problems as text, and a file its
markers name that cannot be read.
"""

from __future__ import annotations

import importlib.util
import json
import os
import reprlib
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

from mcgyvr.serving import gatelib
from mcgyvr.serving.gatelib import refuse

#: Where a campaign's folder sits under the run root.
CAMPAIGNS = Path("tools") / "runs" / "campaigns"
#: The serving harness's marker list and its check, under the run root.
LAUNCH = Path("tools") / "bench" / "serving" / "launch.py"
#: The module name the root's ``launch.py`` is loaded under.
MODULE = "_serving_launch"


def failure(error: BaseException) -> str:
    """An error as a refusal names it: its type, then its message."""
    return f"{type(error).__name__}: {error}"


def run_root() -> Path:
    """``RUN_ROOT``, which must name a folder."""
    given = gatelib.root()
    try:
        folder = stat.S_ISDIR(given.stat().st_mode)
    except FileNotFoundError:
        folder = False
    except OSError as error:
        refuse(f"RUN_ROOT {str(given)!r} cannot be looked at: {failure(error)}")
    if not folder:
        refuse(f"RUN_ROOT {str(given)!r} is not a folder")
    return given


def campaign() -> str:
    """``RUN_CAMPAIGN``: the name of one campaign folder. Absent or empty, the
    gate has no campaign to check.

    Read here, not through ``gatelib.need``, whose refusal says an empty
    variable means the gate was started outside the door: the door's ``read``
    names no campaign.
    """
    name = os.environ.get("RUN_CAMPAIGN")
    if not name:
        refuse(
            "RUN_CAMPAIGN is not set or is empty; this gate checks the campaign "
            "a door names there, and was given none"
        )
    if name in (".", "..") or Path(name).name != name:
        refuse(f"RUN_CAMPAIGN {name!r} is not the name of one campaign folder")
    return name


def declaration(tree: Path, name: str) -> dict[str, Any] | None:
    """The campaign's ``campaign.json``, or ``None`` when nothing is at its path."""
    path = tree / CAMPAIGNS / name / "campaign.json"
    try:
        path.lstat()
    except FileNotFoundError:
        return None
    except OSError as error:
        refuse(f"{str(path)!r} cannot be looked at: {failure(error)}")
    try:
        # A pipe or a folder is not read: a pipe would hold the gate forever.
        if not stat.S_ISREG(path.stat().st_mode):
            refuse(f"{str(path)!r} is not a file")
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        refuse(f"{str(path)!r} cannot be read as JSON: {failure(error)}")
    if not isinstance(doc, dict):
        refuse(f"{str(path)!r} is not a JSON object")
    return doc


def verifier(tree: Path) -> tuple[ModuleType, Callable[[Path], object]]:
    """The root's ``launch.py``, loaded with the root first on the import path,
    as gate 2b loads it, and its ``verify_markers``."""
    path = tree / LAUNCH
    try:
        regular = stat.S_ISREG(path.stat().st_mode)
    except FileNotFoundError:
        regular = False
    except OSError as error:
        refuse(f"{str(path)!r} cannot be looked at: {failure(error)}")
    if not regular:
        refuse(
            f"{LAUNCH.as_posix()} is not a file under {str(tree)!r}; a serving "
            "campaign's markers are listed there"
        )
    spec = importlib.util.spec_from_file_location(MODULE, path)
    if spec is None or spec.loader is None:
        refuse(f"{str(path)!r} cannot be loaded as a module")
    module = importlib.util.module_from_spec(spec)
    # Registered before it runs, as an import registers a module: a dataclass
    # in the harness looks its module up by name while it is being defined.
    sys.modules[MODULE] = module
    sys.path.insert(0, str(tree))
    try:
        spec.loader.exec_module(module)
        verify: Callable[[Path], object] = module.verify_markers
    # SystemExit too: a harness that exits while it loads has not been checked.
    except (Exception, SystemExit) as error:
        refuse(
            f"{str(path)!r} cannot be loaded for its verify_markers: {failure(error)}"
        )
    return module, verify


def unreadable(tree: Path, module: ModuleType) -> list[str]:
    """The files the harness's marker lists name that cannot be read as UTF-8."""
    try:
        listed = (*getattr(module, "MARKERS", ()), *getattr(module, "WITHDRAWN", ()))
        names = sorted({str(entry[0]) for entry in listed})
    except Exception:
        return []
    found: list[str] = []
    for name in names:
        try:
            (tree / name).read_text(encoding="utf-8")
        except (OSError, ValueError):
            found.append(name)
    return found


def problems(tree: Path) -> list[str]:
    """``verify_markers`` of the root's harness, over the root."""
    module, verify = verifier(tree)
    harness = str(tree / LAUNCH)
    try:
        found = verify(tree)
    except UnicodeDecodeError as error:
        named = unreadable(tree, module)
        refuse(
            f"a file the serving markers name cannot be read as UTF-8 text under "
            f"{str(tree)!r}"
            + (f": {', '.join(named)}" if named else "")
            + f" ({failure(error)})"
        )
    except (Exception, SystemExit) as error:
        refuse(f"verify_markers of {harness!r} failed: {failure(error)}")
    if not isinstance(found, list) or not all(isinstance(line, str) for line in found):
        refuse(
            f"verify_markers of {harness!r} returned {reprlib.repr(found)}, not a "
            "list of problems as text"
        )
    return found


def main() -> int:
    where = run_root()
    name = campaign()
    doc = declaration(where, name)
    if doc is None:
        print(f"serving markers: campaign {name!r} has no campaign.json; not checked")
        return 0
    if doc.get("serving") is not True:
        print(f"serving markers: campaign {name!r} does not serve; not checked")
        return 0
    found = problems(where)
    if found:
        refuse("the serving harness on disk fails its own markers: " + "; ".join(found))
    print(f"serving markers: campaign {name!r} serves; its harness holds them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""The serving harness's markers, checked before a serving campaign's step.

The campaign marker check is the lab's (owner ruling): it checks that the
serving harness on disk is the harness that was edited, which is measuring,
not serving. This is the lab's gate for it, written for the gate list a
caller is to hand the door's step verb, in phase ``after``: it runs once the
door has leased and read the machine, and before the step. The product's
door has no step verb yet. Until it has, a campaign reaches the door through
its campaign entry, whose gate 2b imports ``verify_markers`` from the run
root's harness, with the root first on the import path, and runs it over the
root. This gate puts the root first too, but loads the harness file by its
path, so a relative import in it, which 2b's import by name resolves, is
refused here. Where the check cannot be made as asked, this gate refuses,
naming what failed, where 2b may pass or end in a traceback. The door's
``serve`` names its campaign ``live-<host>``, which has no campaign folder,
so it is not checked; ``read`` names none, which this gate refuses. So the
gate goes only on the step verb's list. Which name carries the campaign to
this gate under the step verb is for the verb to settle.

The gate exports nothing. Of the product it uses only the door's library for
its gates, ``gatelib``: ``refuse``, so a refusal has the form and exit status
of the door's own gates, and ``root``, which reads ``RUN_ROOT`` as they do. It
does not call ``gatelib.door_required``, which the product's own gate scripts
call: it reaches no machine and writes nothing, and it checks the tree it is
given, so a run by hand, with ``RUN_ROOT`` and ``RUN_CAMPAIGN`` typed in,
checks that tree as a door run would. Whether it calls it once the step
verb's list names it is for that list to settle.

It reads the run from the environment a door gives its gates: ``RUN_ROOT``,
the tree the run runs from, and ``RUN_CAMPAIGN``. When
``tools/runs/campaigns/<RUN_CAMPAIGN>/campaign.json`` under the root says
``"serving": true``, it loads ``verify_markers`` from the root's
``tools/bench/serving/launch.py``, with the root first on the import path,
and runs it over the root; any problem is a refusal, exit 2, naming every
marker that fails. Links are followed. A campaign whose ``campaign.json``
path's lstat finds no such file, or whose ``campaign.json`` does not say
``"serving": true``, is not held to the serving markers, and the gate says
which of the two it found. Each of these is refused with exit 2, naming what
failed, and without a traceback: an unset or empty ``RUN_ROOT`` or
``RUN_CAMPAIGN``; a root that is not a folder or cannot be looked at; a
campaign name that is not one folder name; a ``campaign.json`` path that
cannot be looked at (as when the campaign name names a file), is not a file,
cannot be read or is not a JSON object; for a serving campaign, a
``launch.py`` that cannot be looked at, is not a file or cannot be loaded,
and a ``verify_markers`` that fails, exits or does not return a list of
problems as text. When ``verify_markers`` fails on text that is not UTF-8,
the refusal names the files the markers list that are there and are not
UTF-8; when it finds none, the refusal names the failure alone. Every root
and file name the gate words itself is printed escaped; the problems
``verify_markers`` returns are printed as the harness words them.
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
    """``RUN_ROOT``, which must name a folder.

    Absent or empty, it is refused here, before ``gatelib.root``, whose
    refusal says only that it is not set.
    """
    if not os.environ.get("RUN_ROOT"):
        refuse(
            "RUN_ROOT is not set or is empty; this gate checks the tree a door "
            "names there, and was given none"
        )
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
    """The campaign's ``campaign.json``, or ``None`` when the lstat of its path
    finds no such file."""
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
    """The root's ``launch.py`` and its ``verify_markers``.

    The root is put first on the import path, as gate 2b puts it, but the file
    is loaded by its path, where 2b imports it by name: a relative import in
    it, which 2b resolves, is refused here as a harness that cannot be loaded.
    """
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


def undecodable(tree: Path, module: ModuleType) -> list[str]:
    """The files the harness's marker lists name that are there and are not
    UTF-8 text. A file that cannot be opened is not one of them; a list that
    cannot be walked names none."""
    try:
        listed = (*getattr(module, "MARKERS", ()), *getattr(module, "WITHDRAWN", ()))
        names = sorted({str(entry[0]) for entry in listed})
    except Exception:
        return []
    found: list[str] = []
    for name in names:
        try:
            (tree / name).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            found.append(name)
        except (OSError, ValueError):
            continue
    return found


def problems(tree: Path) -> list[str]:
    """``verify_markers`` of the root's harness, over the root."""
    module, verify = verifier(tree)
    harness = str(tree / LAUNCH)
    try:
        found = verify(tree)
    # SystemExit too: a check that exits has not been made.
    except (Exception, SystemExit) as error:
        named = []
        if isinstance(error, UnicodeDecodeError):
            named = undecodable(tree, module)
        if named:
            refuse(
                f"a file the serving markers name cannot be read as UTF-8 text "
                f"under {str(tree)!r}: {', '.join(repr(name) for name in named)} "
                f"({failure(error)})"
            )
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

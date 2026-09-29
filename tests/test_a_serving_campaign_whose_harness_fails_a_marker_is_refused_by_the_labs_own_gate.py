"""A serving campaign is refused by the lab's own gate when its harness fails a marker.

The campaign marker check is the lab's: it checks that the serving harness on
disk is the harness that was edited, and that is measuring, not serving. So
the lab holds the gate that runs it, ``tools/door/serving_markers.py``. Of the
product the gate may import only the door's library for its gates,
``gatelib``: every run of it here is a process in which any other module of
the product fails to import, started from a folder that is not the tree it
checks.

The gate reads the run from the environment a door gives its gates:
``RUN_ROOT`` (the tree the run runs from) and ``RUN_CAMPAIGN``. When
``tools/runs/campaigns/<RUN_CAMPAIGN>/campaign.json`` under the root says
``"serving": true``, it runs ``verify_markers`` of the root's own
``tools/bench/serving/launch.py`` over the root, with the root first on the
import path, and any problem refuses with exit 2, naming every marker that
fails. A campaign that does not serve is not held to the serving markers, and
the gate says whether it found no ``campaign.json`` or one that does not
serve. A run the gate cannot name, a root that is not a folder or cannot be
looked at, a ``campaign.json`` that cannot be looked at or read or is not a
JSON object, a harness that cannot be loaded, a ``verify_markers`` that fails
or does not return a list of problems, and a file the markers name that
cannot be read are each refused with exit 2, naming what failed, and without
a traceback.

The tree the gate checks is a throw-away copy of the harness files the
markers name, with markers broken on purpose where a test says so.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import types
from collections.abc import Callable
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
GATE = REPO / "tools" / "door" / "serving_markers.py"
LAUNCH = Path("tools") / "bench" / "serving" / "launch.py"
CAMPAIGNS = Path("tools") / "runs" / "campaigns"
CAMPAIGN = "fixture"
#: A marker only a test's root lists: no harness file carries it.
OWN_MARKER = "A MARKER ONLY THIS ROOT LISTS"
#: How every refusal of the gate begins: its file name, as the door's gates
#: name themselves.
REFUSAL = "serving_markers.py: "
#: What the gate prints when a serving campaign's harness holds its markers.
HOLDS = "its harness holds them"
#: A campaign name with a control character in it.
ODD = "odd\x1b[2Jname"
#: The line that opens the harness's marker list.
MARKERS_HEAD = "MARKERS: tuple[tuple[str, str, str], ...] = (\n"

#: The gate, run as a script, in a process where the door's ``gatelib`` is the
#: only module of the product that can be imported. It is imported first; then
#: every other module of the product is forgotten, the packages above it are
#: replaced by empty ones, and any later import of the product fails. A gate
#: that needed more of ``mcgyvr`` would end in an ImportError, never in the
#: exit 0 or 2 these tests expect.
NO_PRODUCT = """\
import runpy
import sys
import types

import mcgyvr.serving.gatelib as gatelib

for name in [n for n in sys.modules if n == "mcgyvr" or n.startswith("mcgyvr.")]:
    del sys.modules[name]
product = types.ModuleType("mcgyvr")
product.__path__ = []
serving = types.ModuleType("mcgyvr.serving")
serving.__path__ = []
product.serving = serving
serving.gatelib = gatelib
sys.modules.update(
    {"mcgyvr": product, "mcgyvr.serving": serving, "mcgyvr.serving.gatelib": gatelib}
)


class NoProduct:
    def find_spec(self, name, path=None, target=None):
        if name == "mcgyvr" or name.startswith("mcgyvr."):
            raise ImportError(name + " is the product's; the gate may use only gatelib")
        return None


sys.meta_path.insert(0, NoProduct())
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


def _launch() -> types.ModuleType:
    return importlib.import_module("tools.bench.serving.launch")


def _broken() -> tuple[str, str]:
    """The marker most of these tests break: the first the harness lists."""
    path, marker, _decision = _launch().MARKERS[0]
    return str(path), str(marker)


def _only_marked() -> str:
    """The first file the marker list names that the withdrawn list does not."""
    launch = _launch()
    withdrawn = {str(path) for path, _marker, _decision in launch.WITHDRAWN}
    return next(
        str(path)
        for path, _marker, _decision in launch.MARKERS
        if str(path) not in withdrawn
    )


def _remove(root: Path, rel: str, marker: str) -> None:
    text = (root / rel).read_text(encoding="utf-8")
    assert marker in text, f"{rel} no longer carries {marker!r}"
    (root / rel).write_text(text.replace(marker, ""), encoding="utf-8")


def _append(root: Path, text: str) -> None:
    with (root / LAUNCH).open("a", encoding="utf-8") as handle:
        handle.write(text)


def _tree(tmp_path: Path, *, broken: bool) -> Path:
    """The harness's marker list and every file it names, copied; the first
    marker removed when ``broken``."""
    root = tmp_path / "root"
    launch = _launch()
    rels = {LAUNCH.as_posix()} | {
        path for path, _marker, _decision in (*launch.MARKERS, *launch.WITHDRAWN)
    }
    for rel in sorted(rels):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, root / rel)
    if broken:
        _remove(root, *_broken())
    return root


def _campaign(root: Path, doc: object, name: str = CAMPAIGN) -> Path:
    folder = root / CAMPAIGNS / name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "campaign.json"
    path.write_text(json.dumps(doc) + "\n", encoding="utf-8")
    return path


def _unreadable(path: Path) -> None:
    """``path`` at mode 000; the test is skipped for a user who reads it, or
    looks inside it, anyway."""
    path.chmod(0)
    if os.access(path, os.R_OK) or (path.is_dir() and os.access(path, os.X_OK)):
        path.chmod(0o700)
        pytest.skip("this user reads a path at mode 000")


def _gate(root: Path, **run: str | None) -> subprocess.CompletedProcess[str]:
    """The gate over ``root``, started from the folder that holds it, with
    ``RUN_ROOT`` and ``RUN_CAMPAIGN`` as a door sets them unless ``run`` says
    otherwise: ``None`` leaves a variable unset, and any string, the empty one
    too, is set."""
    assert GATE.is_file(), f"the lab holds no marker gate at {GATE.relative_to(REPO)}"
    env = {k: v for k, v in os.environ.items() if not k.startswith("RUN_")}
    wanted: dict[str, str | None] = {
        "RUN_ROOT": str(root),
        "RUN_CAMPAIGN": CAMPAIGN,
        **run,
    }
    env.update({k: v for k, v in wanted.items() if v is not None})
    return subprocess.run(
        [sys.executable, "-c", NO_PRODUCT, str(GATE)],
        cwd=root.parent,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _refused(done: subprocess.CompletedProcess[str]) -> str:
    """The gate's output, once it is known to be a refusal and not a crash."""
    out = done.stdout + done.stderr
    assert done.returncode == 2, f"exit {done.returncode}: {out[-900:]}"
    assert "Traceback" not in done.stderr, out[-900:]
    assert done.stderr.startswith(REFUSAL), f"not the gate's refusal: {out[-900:]}"
    return out


def _passed(done: subprocess.CompletedProcess[str]) -> str:
    out = done.stdout + done.stderr
    assert done.returncode == 0, f"exit {done.returncode}: {out[-900:]}"
    return out


def test_the_gate_runs_where_the_product_offers_only_its_gatelib(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.py"
    probe.write_text(
        "from mcgyvr.serving.gatelib import refuse, root\n"
        "for name in ('mcgyvr.config', 'mcgyvr.serving.vramfit', 'mcgyvr.derived'):\n"
        "    try:\n"
        "        __import__(name)\n"
        "    except ImportError:\n"
        "        continue\n"
        "    raise SystemExit(name + ' was imported')\n"
        "try:\n"
        "    from mcgyvr import config\n"
        "except ImportError:\n"
        "    print('only gatelib')\n",
        encoding="utf-8",
    )
    done = subprocess.run(
        [sys.executable, "-c", NO_PRODUCT, str(probe)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    out = _passed(done)
    assert done.stdout == "only gatelib\n", out[-600:]


def test_a_serving_campaign_with_a_broken_marker_is_refused(tmp_path: Path) -> None:
    root = _tree(tmp_path, broken=True)
    _campaign(root, {"serving": True})
    done = _gate(root)
    out = _refused(done)
    _rel, marker = _broken()
    assert "MISSING" in done.stderr and marker in done.stderr, (
        f"the refusal does not name the missing marker {marker!r}: {out[-600:]}"
    )


def test_a_serving_campaign_is_refused_naming_every_marker_that_fails(
    tmp_path: Path,
) -> None:
    launch = _launch()
    root = _tree(tmp_path, broken=True)
    first_rel, first = _broken()
    last_rel, last, _decision = next(
        entry for entry in reversed(launch.MARKERS) if entry[0] != first_rel
    )
    _remove(root, last_rel, last)
    withdrawn_rel, withdrawn, _decision = launch.WITHDRAWN[0]
    with (root / withdrawn_rel).open("a", encoding="utf-8") as handle:
        handle.write(f"\n{withdrawn}\n")
    _campaign(root, {"serving": True})
    done = _gate(root)
    out = _refused(done)
    for marker in (first, last):
        assert marker in done.stderr, f"{marker!r} is not named: {out[-900:]}"
    assert "STILL PRESENT" in done.stderr and withdrawn in done.stderr, (
        f"the withdrawn {withdrawn!r} put back is not named: {out[-900:]}"
    )


def test_a_serving_campaign_is_held_to_the_markers_its_own_root_lists(
    tmp_path: Path,
) -> None:
    root = _tree(tmp_path, broken=False)
    text = (root / LAUNCH).read_text(encoding="utf-8")
    assert MARKERS_HEAD in text, f"{LAUNCH} opens its marker list otherwise"
    entry = f'    ("tools/bench/observed.py", "{OWN_MARKER}", "a test\'s own"),\n'
    (root / LAUNCH).write_text(
        text.replace(MARKERS_HEAD, MARKERS_HEAD + entry), encoding="utf-8"
    )
    _campaign(root, {"serving": True})
    done = _gate(root)
    out = _refused(done)
    assert OWN_MARKER in done.stderr, (
        f"the refusal does not name the marker the root lists: {out[-600:]}"
    )


def test_a_serving_campaign_whose_markers_hold_passes(tmp_path: Path) -> None:
    root = _tree(tmp_path, broken=False)
    _campaign(root, {"serving": True})
    done = _gate(root)
    out = _passed(done)
    assert HOLDS in done.stdout, out[-600:]


def test_a_harness_that_defines_a_dataclass_is_checked(tmp_path: Path) -> None:
    root = _tree(tmp_path, broken=False)
    _append(
        root,
        "\n\nimport dataclasses\n\n\n@dataclasses.dataclass\nclass _Probe:\n"
        "    name: str\n",
    )
    _campaign(root, {"serving": True})
    done = _gate(root)
    out = _passed(done)
    assert HOLDS in done.stdout, out[-600:]


def test_a_harness_that_imports_from_its_own_tree_is_checked(tmp_path: Path) -> None:
    """The root's harness is loaded with the root first on the import path, as
    the door's campaign entry loads it, so ``tools`` is the root's own."""
    root = _tree(tmp_path, broken=False)
    _append(
        root,
        "\n\nfrom tools.bench.serving import contract as _own\n\n"
        "if not Path(_own.__file__).resolve().is_relative_to(REPO.resolve()):\n"
        "    raise ImportError(f'{_own.__file__} is not under {REPO}')\n",
    )
    _campaign(root, {"serving": True})
    done = _gate(root)
    out = _passed(done)
    assert HOLDS in done.stdout, out[-600:]


@pytest.mark.parametrize(
    "doc",
    [{"serving": False}, {}, {"serving": "true"}, {"serving": 1}],
    ids=["serving-false", "serving-unsaid", "serving-a-string", "serving-a-number"],
)
def test_a_campaign_that_does_not_serve_is_not_held_to_the_markers(
    tmp_path: Path, doc: dict[str, object]
) -> None:
    root = _tree(tmp_path, broken=True)
    _campaign(root, doc)
    done = _gate(root)
    out = _passed(done)
    _rel, marker = _broken()
    assert marker not in out and "MISSING" not in out, out[-600:]
    assert "does not serve" in done.stdout, out[-600:]


def test_a_campaign_with_no_campaign_json_is_said_to_have_none(
    tmp_path: Path,
) -> None:
    root = _tree(tmp_path, broken=True)
    done = _gate(root)
    out = _passed(done)
    _rel, marker = _broken()
    assert marker not in out and "MISSING" not in out, out[-600:]
    assert "no campaign.json" in done.stdout, out[-600:]


def test_a_campaign_that_does_not_serve_needs_no_marker_list(tmp_path: Path) -> None:
    root = _tree(tmp_path, broken=False)
    _campaign(root, {"serving": False})
    (root / LAUNCH).unlink()
    _passed(_gate(root))


@pytest.mark.parametrize(
    ("doc", "said"),
    [
        (None, "no campaign.json"),
        ({"serving": False}, "does not serve"),
        ({"serving": True}, HOLDS),
        ("{not json\n", "cannot be read as JSON"),
    ],
    ids=["no-campaign-json", "does-not-serve", "serves", "refused"],
)
def test_a_campaign_name_is_printed_with_its_control_characters_escaped(
    tmp_path: Path, doc: object, said: str
) -> None:
    root = _tree(tmp_path, broken=False)
    if isinstance(doc, str):
        _campaign(root, {}, name=ODD).write_text(doc, encoding="utf-8")
    elif doc is not None:
        _campaign(root, doc, name=ODD)
    done = _gate(root, RUN_CAMPAIGN=ODD)
    out = done.stdout + done.stderr
    assert done.returncode == (2 if isinstance(doc, str) else 0), (
        f"exit {done.returncode}: {out[-600:]!r}"
    )
    assert said in out, f"{said!r} is not said: {out[-600:]!r}"
    assert "\x1b" not in out, f"a control character is printed raw: {out[-600:]!r}"
    assert "odd\\x1b[2Jname" in out, out[-600:]


@pytest.mark.parametrize(
    ("run", "named"),
    [
        ({"RUN_CAMPAIGN": None}, "RUN_CAMPAIGN"),
        ({"RUN_CAMPAIGN": ""}, "RUN_CAMPAIGN"),
        ({"RUN_ROOT": None}, "RUN_ROOT"),
        ({"RUN_ROOT": ""}, "RUN_ROOT"),
        ({"RUN_CAMPAIGN": "../fixture"}, "../fixture"),
        ({"RUN_CAMPAIGN": ".."}, ".."),
    ],
    ids=[
        "campaign-unset",
        "campaign-empty",
        "root-unset",
        "root-empty",
        "campaign-with-a-slash",
        "campaign-dot-dot",
    ],
)
def test_a_run_the_gate_cannot_name_is_refused(
    tmp_path: Path, run: dict[str, str | None], named: str
) -> None:
    root = _tree(tmp_path, broken=True)
    _campaign(root, {"serving": True})
    done = _gate(root, **run)
    out = _refused(done)
    assert named in done.stderr, f"the refusal does not name {named!r}: {out[-600:]}"


@pytest.mark.parametrize("key", ["RUN_CAMPAIGN", "RUN_ROOT"])
def test_a_run_variable_set_empty_is_refused_as_empty(tmp_path: Path, key: str) -> None:
    root = _tree(tmp_path, broken=True)
    _campaign(root, {"serving": True})
    done = _gate(root, **{key: ""})
    out = _refused(done)
    assert key in done.stderr and "empty" in done.stderr, (
        f"the refusal does not say {key} is empty: {out[-600:]}"
    )


@pytest.mark.parametrize("kind", ["missing", "a-file", "in-a-locked-folder"])
def test_a_run_root_that_is_not_a_folder_is_refused(tmp_path: Path, kind: str) -> None:
    root = _tree(tmp_path, broken=True)
    _campaign(root, {"serving": True})
    locked = tmp_path / "locked"
    given = {
        "missing": tmp_path / "nowhere",
        "a-file": root / LAUNCH,
        "in-a-locked-folder": locked / "root",
    }[kind]
    if kind == "in-a-locked-folder":
        given.mkdir(parents=True)
        _unreadable(locked)
    try:
        done = _gate(root, RUN_ROOT=str(given))
    finally:
        if locked.exists():
            locked.chmod(0o700)
    out = _refused(done)
    assert str(given) in done.stderr, f"the refusal does not name {given}: {out[-600:]}"
    if kind == "in-a-locked-folder":
        assert "cannot be looked at" in done.stderr, out[-600:]


def _not_json(path: Path) -> None:
    path.write_text("{not json\n", encoding="utf-8")


def _not_an_object(path: Path) -> None:
    path.write_text("[true]\n", encoding="utf-8")


def _nested_too_deep(path: Path) -> None:
    path.write_text("[" * 100_000 + "]" * 100_000 + "\n", encoding="utf-8")


def _a_link_to_nothing(path: Path) -> None:
    path.unlink()
    path.symlink_to(path.parent / "nowhere.json")


def _a_folder(path: Path) -> None:
    path.unlink()
    path.mkdir()


def _a_pipe(path: Path) -> None:
    path.unlink()
    os.mkfifo(path)


def _in_a_locked_folder(path: Path) -> None:
    _unreadable(path.parent)


@pytest.mark.parametrize(
    "spoil",
    [
        _not_json,
        _not_an_object,
        _nested_too_deep,
        _unreadable,
        _a_link_to_nothing,
        _a_folder,
        _a_pipe,
        _in_a_locked_folder,
    ],
    ids=[
        "not-json",
        "not-an-object",
        "nested-too-deep",
        "unreadable",
        "a-link-to-nothing",
        "a-folder",
        "a-pipe",
        "in-a-locked-folder",
    ],
)
def test_a_campaign_json_the_gate_cannot_read_or_that_is_not_an_object_is_refused(
    tmp_path: Path, spoil: Callable[[Path], None]
) -> None:
    root = _tree(tmp_path, broken=True)
    path = _campaign(root, {"serving": False})
    spoil(path)
    try:
        done = _gate(root)
    finally:
        path.parent.chmod(0o700)
    out = _refused(done)
    assert str(path) in done.stderr, f"the refusal does not name {path}: {out[-600:]}"


@pytest.mark.parametrize("kind", ["missing", "a-folder"])
def test_a_serving_campaign_whose_root_holds_no_marker_list_file_is_refused(
    tmp_path: Path, kind: str
) -> None:
    root = _tree(tmp_path, broken=False)
    _campaign(root, {"serving": True})
    (root / LAUNCH).unlink()
    if kind == "a-folder":
        (root / LAUNCH).mkdir()
    done = _gate(root)
    out = _refused(done)
    assert f"{LAUNCH.as_posix()} is not a file under" in done.stderr, out[-600:]


def _launch_unreadable(root: Path) -> str:
    _unreadable(root / LAUNCH)
    return LAUNCH.as_posix()


def _launch_that_does_not_parse(root: Path) -> str:
    _append(root, "\ndef (\n")
    return LAUNCH.as_posix()


def _launch_without_verify_markers(root: Path) -> str:
    text = (root / LAUNCH).read_text(encoding="utf-8")
    assert "def verify_markers(" in text
    text = text.replace("def verify_markers(", "def verify_markers_gone(")
    (root / LAUNCH).write_text(text, encoding="utf-8")
    return LAUNCH.as_posix()


def _launch_importing_a_missing_module(root: Path) -> str:
    _append(root, "\nimport no_such_module_of_the_harness\n")
    return LAUNCH.as_posix()


def _launch_naming_an_undefined_name(root: Path) -> str:
    _append(root, "\nno_such_name_in_the_harness\n")
    return LAUNCH.as_posix()


def _launch_that_exits_while_it_loads(root: Path) -> str:
    _append(root, "\nraise SystemExit(0)\n")
    return LAUNCH.as_posix()


def _marker_file_not_utf8(root: Path) -> str:
    rel = _only_marked()
    (root / rel).write_bytes(b"\xff\xfe not UTF-8 text\n")
    return rel


def _marker_file_missing(root: Path) -> str:
    rel, _marker = _broken()
    (root / rel).unlink()
    return rel


def _marker_file_unreadable(root: Path) -> str:
    rel, _marker = _broken()
    _unreadable(root / rel)
    return rel


@pytest.mark.parametrize(
    "spoil",
    [
        _launch_unreadable,
        _launch_that_does_not_parse,
        _launch_without_verify_markers,
        _launch_importing_a_missing_module,
        _launch_naming_an_undefined_name,
        _launch_that_exits_while_it_loads,
        _marker_file_not_utf8,
        _marker_file_missing,
        _marker_file_unreadable,
    ],
    ids=[
        "launch-unreadable",
        "launch-does-not-parse",
        "launch-without-verify-markers",
        "launch-importing-a-missing-module",
        "launch-naming-an-undefined-name",
        "launch-exits-while-it-loads",
        "marker-file-not-utf8",
        "marker-file-missing",
        "marker-file-unreadable",
    ],
)
def test_a_harness_file_the_gate_cannot_load_or_read_is_refused_naming_it(
    tmp_path: Path, spoil: Callable[[Path], str]
) -> None:
    root = _tree(tmp_path, broken=False)
    _campaign(root, {"serving": True})
    named = spoil(root)
    done = _gate(root)
    out = _refused(done)
    assert named in done.stderr, f"the refusal does not name {named}: {out[-900:]}"


@pytest.mark.parametrize(
    "verify",
    [
        "verify_markers = None\n",
        "def verify_markers():\n    return []\n",
        "def verify_markers(repo):\n    return None\n",
        "def verify_markers(repo):\n    return [1]\n",
        "def verify_markers(repo):\n    raise RuntimeError('a check that broke')\n",
    ],
    ids=[
        "not-a-function",
        "a-wrong-signature",
        "returns-no-list",
        "returns-no-text",
        "raises",
    ],
)
def test_a_verify_markers_that_fails_or_returns_no_list_of_problems_is_refused(
    tmp_path: Path, verify: str
) -> None:
    root = _tree(tmp_path, broken=True)
    _append(root, "\n\n" + verify)
    _campaign(root, {"serving": True})
    done = _gate(root)
    out = _refused(done)
    assert LAUNCH.as_posix() in done.stderr, out[-900:]


def test_a_marker_list_the_harness_cannot_walk_is_not_called_unreadable_text(
    tmp_path: Path,
) -> None:
    root = _tree(tmp_path, broken=False)
    text = (root / LAUNCH).read_text(encoding="utf-8")
    assert MARKERS_HEAD in text, f"{LAUNCH} opens its marker list otherwise"
    entry = f'    ("{_only_marked()}", "a marker with no decision"),\n'
    (root / LAUNCH).write_text(
        text.replace(MARKERS_HEAD, MARKERS_HEAD + entry), encoding="utf-8"
    )
    _campaign(root, {"serving": True})
    done = _gate(root)
    out = _refused(done)
    assert "ValueError" in done.stderr and LAUNCH.as_posix() in done.stderr, out[-900:]
    assert "UTF-8" not in done.stderr, f"not a text that cannot be read: {out[-900:]}"

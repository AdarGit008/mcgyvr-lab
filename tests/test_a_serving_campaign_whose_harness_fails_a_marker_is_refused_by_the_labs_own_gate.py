"""A serving campaign is refused by the lab's own gate when its harness fails a marker.

The campaign marker check is the lab's: it checks that the serving harness on
disk is the harness that was edited, and that is measuring, not serving. So
the lab holds the gate that runs it, ``tools/door/serving_markers.py``, and
the gate needs nothing of the product: every run of it here is a process in
which importing ``mcgyvr`` fails, started from a folder that is not the tree
it checks.

The gate reads the run from the environment a door gives its gates:
``RUN_ROOT`` (the tree the run runs from) and ``RUN_CAMPAIGN``. When
``tools/runs/campaigns/<RUN_CAMPAIGN>/campaign.json`` under the root says
``"serving": true``, it runs ``verify_markers`` of the root's own
``tools/bench/serving/launch.py`` over the root, and any problem refuses with
exit 2, naming every marker that fails. A campaign that does not serve is not
held to the serving markers, and the gate says whether it found no
``campaign.json`` or one that does not serve. A run the gate cannot name, a
root that is not a folder, a ``campaign.json`` it cannot read or that is not a
JSON object, and a harness file it cannot load or read are refused with exit
2, naming what failed.

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

#: The gate, run as a script, in a process where any import of the product's
#: package fails. A gate that needed ``mcgyvr`` would end in an ImportError,
#: never in the exit 0 or 2 these tests expect.
NO_PRODUCT = """\
import runpy
import sys


class NoProduct:
    def find_spec(self, name, path=None, target=None):
        if name == "mcgyvr" or name.startswith("mcgyvr."):
            raise ImportError(name + " is the product's; the gate needs none of it")
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


def _remove(root: Path, rel: str, marker: str) -> None:
    text = (root / rel).read_text(encoding="utf-8")
    assert marker in text, f"{rel} no longer carries {marker!r}"
    (root / rel).write_text(text.replace(marker, ""), encoding="utf-8")


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


def _campaign(root: Path, doc: object) -> Path:
    folder = root / CAMPAIGNS / CAMPAIGN
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "campaign.json"
    path.write_text(json.dumps(doc) + "\n", encoding="utf-8")
    return path


def _unreadable(path: Path) -> None:
    """``path`` at mode 000; the test is skipped for a user who reads it anyway."""
    path.chmod(0)
    if os.access(path, os.R_OK):
        pytest.skip("this user reads a file at mode 000")


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


def test_a_serving_campaign_with_a_broken_marker_is_refused(tmp_path: Path) -> None:
    root = _tree(tmp_path, broken=True)
    _campaign(root, {"serving": True})
    done = _gate(root)
    out = done.stdout + done.stderr
    assert done.returncode == 2, f"exit {done.returncode}: {out[-600:]}"
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
    out = done.stdout + done.stderr
    assert done.returncode == 2, f"exit {done.returncode}: {out[-600:]}"
    for marker in (first, last):
        assert marker in done.stderr, f"{marker!r} is not named: {out[-900:]}"
    assert "STILL PRESENT" in done.stderr and withdrawn in done.stderr, (
        f"the withdrawn {withdrawn!r} put back is not named: {out[-900:]}"
    )


def test_a_serving_campaign_is_held_to_the_markers_its_own_root_lists(
    tmp_path: Path,
) -> None:
    root = _tree(tmp_path, broken=False)
    head = "MARKERS: tuple[tuple[str, str, str], ...] = (\n"
    text = (root / LAUNCH).read_text(encoding="utf-8")
    assert head in text, f"{LAUNCH} no longer opens its marker list with {head!r}"
    entry = f'    ("tools/bench/observed.py", "{OWN_MARKER}", "a test\'s own"),\n'
    (root / LAUNCH).write_text(text.replace(head, head + entry), encoding="utf-8")
    _campaign(root, {"serving": True})
    done = _gate(root)
    out = done.stdout + done.stderr
    assert done.returncode == 2, f"exit {done.returncode}: {out[-600:]}"
    assert OWN_MARKER in done.stderr, (
        f"the refusal does not name the marker the root lists: {out[-600:]}"
    )


def test_a_serving_campaign_whose_markers_hold_passes(tmp_path: Path) -> None:
    root = _tree(tmp_path, broken=False)
    _campaign(root, {"serving": True})
    done = _gate(root)
    out = done.stdout + done.stderr
    assert done.returncode == 0, f"exit {done.returncode}: {out[-600:]}"


def test_a_harness_that_defines_a_dataclass_is_checked(tmp_path: Path) -> None:
    root = _tree(tmp_path, broken=False)
    with (root / LAUNCH).open("a", encoding="utf-8") as handle:
        handle.write(
            "\n\nimport dataclasses\n\n\n"
            "@dataclasses.dataclass\nclass _Probe:\n    name: str\n"
        )
    _campaign(root, {"serving": True})
    done = _gate(root)
    out = done.stdout + done.stderr
    assert done.returncode == 0, f"exit {done.returncode}: {out[-900:]}"


@pytest.mark.parametrize(
    "doc",
    [{"serving": False}, {}],
    ids=["serving-false", "serving-unsaid"],
)
def test_a_campaign_that_does_not_serve_is_not_held_to_the_markers(
    tmp_path: Path, doc: dict[str, bool]
) -> None:
    root = _tree(tmp_path, broken=True)
    _campaign(root, doc)
    done = _gate(root)
    out = done.stdout + done.stderr
    _rel, marker = _broken()
    assert done.returncode == 0, f"exit {done.returncode}: {out[-600:]}"
    assert marker not in out and "MISSING" not in out, out[-600:]
    assert "does not serve" in done.stdout, out[-600:]


def test_a_campaign_with_no_campaign_json_is_said_to_have_none(
    tmp_path: Path,
) -> None:
    root = _tree(tmp_path, broken=True)
    done = _gate(root)
    out = done.stdout + done.stderr
    _rel, marker = _broken()
    assert done.returncode == 0, f"exit {done.returncode}: {out[-600:]}"
    assert marker not in out and "MISSING" not in out, out[-600:]
    assert "no campaign.json" in done.stdout, out[-600:]


def test_a_campaign_that_does_not_serve_needs_no_marker_list(tmp_path: Path) -> None:
    root = _tree(tmp_path, broken=False)
    _campaign(root, {"serving": False})
    (root / LAUNCH).unlink()
    done = _gate(root)
    out = done.stdout + done.stderr
    assert done.returncode == 0, f"exit {done.returncode}: {out[-600:]}"


def test_a_campaign_name_is_printed_with_its_control_characters_escaped(
    tmp_path: Path,
) -> None:
    root = _tree(tmp_path, broken=False)
    done = _gate(root, RUN_CAMPAIGN="odd\x1b[2Jname")
    out = done.stdout + done.stderr
    assert done.returncode == 0, f"exit {done.returncode}: {out[-600:]!r}"
    assert "\x1b" not in out, f"a control character is printed raw: {out[-600:]!r}"
    assert "odd\\x1b[2Jname" in done.stdout, out[-600:]


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
    out = done.stdout + done.stderr
    assert done.returncode == 2, f"exit {done.returncode}: {out[-600:]}"
    assert named in done.stderr, f"the refusal does not name {named!r}: {out[-600:]}"


@pytest.mark.parametrize("kind", ["missing", "a-file"])
def test_a_run_root_that_is_not_a_folder_is_refused(tmp_path: Path, kind: str) -> None:
    root = _tree(tmp_path, broken=True)
    _campaign(root, {"serving": True})
    given = tmp_path / "nowhere" if kind == "missing" else root / LAUNCH
    done = _gate(root, RUN_ROOT=str(given))
    out = done.stdout + done.stderr
    assert done.returncode == 2, f"exit {done.returncode}: {out[-600:]}"
    assert str(given) in done.stderr, f"the refusal does not name {given}: {out[-600:]}"


@pytest.mark.parametrize(
    "text",
    ["{not json\n", "[true]\n", None],
    ids=["not-json", "not-an-object", "unreadable"],
)
def test_a_campaign_json_the_gate_cannot_read_or_that_is_not_an_object_is_refused(
    tmp_path: Path, text: str | None
) -> None:
    root = _tree(tmp_path, broken=False)
    path = _campaign(root, {"serving": True})
    if text is None:
        _unreadable(path)
    else:
        path.write_text(text, encoding="utf-8")
    done = _gate(root)
    out = done.stdout + done.stderr
    assert done.returncode == 2, f"exit {done.returncode}: {out[-600:]}"
    assert str(path) in done.stderr, f"the refusal does not name {path}: {out[-600:]}"


def test_a_serving_campaign_whose_root_holds_no_marker_list_is_refused(
    tmp_path: Path,
) -> None:
    root = _tree(tmp_path, broken=False)
    _campaign(root, {"serving": True})
    (root / LAUNCH).unlink()
    done = _gate(root)
    out = done.stdout + done.stderr
    assert done.returncode == 2, f"exit {done.returncode}: {out[-600:]}"
    assert LAUNCH.as_posix() in done.stderr, out[-600:]


def _launch_unreadable(root: Path) -> str:
    _unreadable(root / LAUNCH)
    return LAUNCH.as_posix()


def _launch_that_does_not_parse(root: Path) -> str:
    with (root / LAUNCH).open("a", encoding="utf-8") as handle:
        handle.write("\ndef (\n")
    return LAUNCH.as_posix()


def _launch_without_verify_markers(root: Path) -> str:
    text = (root / LAUNCH).read_text(encoding="utf-8")
    assert "def verify_markers(" in text
    text = text.replace("def verify_markers(", "def verify_markers_gone(")
    (root / LAUNCH).write_text(text, encoding="utf-8")
    return LAUNCH.as_posix()


def _marker_file_not_utf8(root: Path) -> str:
    rel, _marker = _broken()
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
        _marker_file_not_utf8,
        _marker_file_missing,
        _marker_file_unreadable,
    ],
    ids=[
        "launch-unreadable",
        "launch-does-not-parse",
        "launch-without-verify-markers",
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
    out = done.stdout + done.stderr
    assert done.returncode == 2, f"exit {done.returncode}: {out[-900:]}"
    assert "Traceback" not in done.stderr, out[-900:]
    assert named in done.stderr, f"the refusal does not name {named}: {out[-900:]}"

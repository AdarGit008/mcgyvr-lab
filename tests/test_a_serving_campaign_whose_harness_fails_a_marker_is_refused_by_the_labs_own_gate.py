"""A serving campaign is refused by the lab's own gate when its harness fails a marker.

The campaign marker check is the lab's: it checks that the serving harness on
disk is the harness that was edited, and that is measuring, not serving. So
the lab holds the gate that runs it, ``tools/door/serving_markers.py``, and
the gate needs nothing of the product: every run of it here is a process in
which importing ``mcgyvr`` fails.

The gate reads the run from the environment a door gives its gates:
``RUN_ROOT`` (the tree the run runs from) and ``RUN_CAMPAIGN``. When
``tools/runs/campaigns/<RUN_CAMPAIGN>/campaign.json`` under the root says
``"serving": true``, it runs ``verify_markers`` of the root's
``tools/bench/serving/launch.py`` over the root, and any problem refuses with
exit 2 and names the marker. A campaign that does not serve is not held to the
serving markers. A run the gate cannot name, or a ``campaign.json`` it cannot
read, is refused and says why.

The tree the gate checks is a throw-away copy of the harness files the
markers name, with one marker broken on purpose where a test says so.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
GATE = REPO / "tools" / "door" / "serving_markers.py"
LAUNCH = Path("tools") / "bench" / "serving" / "launch.py"
CAMPAIGNS = Path("tools") / "runs" / "campaigns"
CAMPAIGN = "fixture"

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
    """The marker these tests break: the first the harness lists."""
    path, marker, _decision = _launch().MARKERS[0]
    return str(path), str(marker)


def _tree(tmp_path: Path, *, broken: bool) -> Path:
    """The harness's marker list and every file it names, copied; one marker
    removed when ``broken``."""
    root = tmp_path / "root"
    launch = _launch()
    rels = {LAUNCH.as_posix()} | {
        path for path, _marker, _decision in (*launch.MARKERS, *launch.WITHDRAWN)
    }
    for rel in sorted(rels):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, root / rel)
    if broken:
        rel, marker = _broken()
        text = (root / rel).read_text(encoding="utf-8")
        assert marker in text, f"{rel} no longer carries {marker!r}"
        (root / rel).write_text(text.replace(marker, ""), encoding="utf-8")
    return root


def _campaign(root: Path, doc: object) -> Path:
    folder = root / CAMPAIGNS / CAMPAIGN
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "campaign.json"
    path.write_text(json.dumps(doc) + "\n", encoding="utf-8")
    return path


def _gate(root: Path, **run: str) -> subprocess.CompletedProcess[str]:
    """The gate over ``root``, with ``RUN_ROOT`` and ``RUN_CAMPAIGN`` as a door
    sets them unless ``run`` says otherwise (an empty value is left unset)."""
    assert GATE.is_file(), f"the lab holds no marker gate at {GATE.relative_to(REPO)}"
    env = {k: v for k, v in os.environ.items() if not k.startswith("RUN_")}
    wanted = {"RUN_ROOT": str(root), "RUN_CAMPAIGN": CAMPAIGN, **run}
    env.update({k: v for k, v in wanted.items() if v})
    return subprocess.run(
        [sys.executable, "-c", NO_PRODUCT, str(GATE)],
        cwd=root,
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


def test_a_serving_campaign_whose_markers_hold_passes(tmp_path: Path) -> None:
    root = _tree(tmp_path, broken=False)
    _campaign(root, {"serving": True})
    done = _gate(root)
    out = done.stdout + done.stderr
    assert done.returncode == 0, f"exit {done.returncode}: {out[-600:]}"


@pytest.mark.parametrize(
    "doc",
    [{"serving": False}, {}, None],
    ids=["serving-false", "serving-unsaid", "no-campaign-json"],
)
def test_a_campaign_that_does_not_serve_is_not_held_to_the_markers(
    tmp_path: Path, doc: dict[str, bool] | None
) -> None:
    root = _tree(tmp_path, broken=True)
    if doc is not None:
        _campaign(root, doc)
    done = _gate(root)
    out = done.stdout + done.stderr
    _rel, marker = _broken()
    assert done.returncode == 0, f"exit {done.returncode}: {out[-600:]}"
    assert marker not in out and "MISSING" not in out, out[-600:]


@pytest.mark.parametrize(
    ("run", "named"),
    [
        ({"RUN_CAMPAIGN": ""}, "RUN_CAMPAIGN"),
        ({"RUN_ROOT": ""}, "RUN_ROOT"),
        ({"RUN_CAMPAIGN": "../fixture"}, "../fixture"),
        ({"RUN_CAMPAIGN": ".."}, ".."),
    ],
    ids=["no-campaign", "no-root", "campaign-with-a-slash", "campaign-dot-dot"],
)
def test_a_run_the_gate_cannot_name_is_refused(
    tmp_path: Path, run: dict[str, str], named: str
) -> None:
    root = _tree(tmp_path, broken=True)
    _campaign(root, {"serving": True})
    done = _gate(root, **run)
    out = done.stdout + done.stderr
    assert done.returncode == 2, f"exit {done.returncode}: {out[-600:]}"
    assert named in done.stderr, f"the refusal does not name {named!r}: {out[-600:]}"


@pytest.mark.parametrize(
    "text", ["{not json\n", "[true]\n"], ids=["not-json", "not-an-object"]
)
def test_a_campaign_json_the_gate_cannot_read_is_refused_naming_it(
    tmp_path: Path, text: str
) -> None:
    root = _tree(tmp_path, broken=False)
    path = _campaign(root, {"serving": True})
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

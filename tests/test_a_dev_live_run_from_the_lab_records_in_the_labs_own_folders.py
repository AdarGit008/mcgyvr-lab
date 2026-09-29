# The lab's own test: written here, not split from any product test.
"""A dev-live run started from the lab records in the lab's own folders.

A product live run keeps no records; a dev-live run, started from the lab,
keeps them (``okf/must-read/the-split.md``). ``tools/live/run.py`` is the
boundary. It sets the data folder and the recording folder to folders of the
lab's own, each named by the product digest and the round it ran under, writes
``tags.json`` beside the recording, and refuses — one line, non-zero — when it
cannot. A developer's run must never land among live ones in
``~/.local/state/mcgyvr``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path
from typing import Any

import yaml

from tests._helpers import PRODUCT, by_path, git

REPO = Path(__file__).resolve().parent.parent
RUN = REPO / "tools" / "live" / "run.py"

#: A minimal valid setup the wrapper loads and re-writes with ``journal.dir``.
#: It names no machine and no model of the owner's: the stub dispatch is the
#: only thing that runs, and it reaches no endpoint.
FLEET = (
    "profile: dev\n"
    "units:\n"
    "  unit-a:\n"
    "    address: http://localhost:8080\n"
    "    model: stub-model\n"
    "    width: 1\n"
)
POLICY = "ladder:\n- unit-a\n"

#: The dispatch the wrapper runs instead of a real model run. It is the test's
#: stand-in for ``mcgyvr run`` and the door: it files one journal row and one
#: reading into the folders the wrapper set, and records the environment it was
#: given so the test can read which folders those were.
STUB = """\
import json
import os
from pathlib import Path

record = Path(os.environ["MCGYVR_RECORD_DIR"])
(record / "agent-a.jsonl").write_text(
    json.dumps({"record_kind": "attempt", "attempt_id": "agent-a:stub:1"}) + "\\n",
    encoding="utf-8",
)
data = Path(os.environ["MCGYVR_DATA"])
(data / "reading.json").write_text(
    json.dumps({"kind": "fleet-reading"}), encoding="utf-8"
)
(data / "env.json").write_text(
    json.dumps(
        {
            "MCGYVR_DATA": os.environ.get("MCGYVR_DATA"),
            "MCGYVR_HOME": os.environ.get("MCGYVR_HOME"),
            "MCGYVR_CONFIG": os.environ.get("MCGYVR_CONFIG"),
            "MCGYVR_RECORD_DIR": os.environ.get("MCGYVR_RECORD_DIR"),
        }
    ),
    encoding="utf-8",
)
"""


def _bench_product() -> types.ModuleType:
    return by_path("bench_product", REPO / "tools" / "bench" / "product.py")


def _digest() -> str:
    return git(PRODUCT, "rev-parse", "HEAD").strip()


def _round_id() -> str:
    return str(_bench_product().open_round()["id"])


def _write_config(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "fleet.yaml").write_text(FLEET, encoding="utf-8")
    (path / "policy.yaml").write_text(POLICY, encoding="utf-8")
    return path


def _write_stub(path: Path) -> Path:
    path.write_text(STUB, encoding="utf-8")
    return path


def _run(
    home: Path, root: Path, config: Path, stub: Path
) -> subprocess.CompletedProcess[str]:
    """Run the wrapper over the stub in a HOME the test owns, off every leak."""
    env = dict(os.environ)
    env["HOME"] = str(home)
    for name in ("MCGYVR_HOME", "MCGYVR_DATA", "MCGYVR_RECORD_DIR", "XDG_STATE_HOME"):
        env.pop(name, None)
    return subprocess.run(
        [
            sys.executable,
            str(RUN),
            "--root",
            str(root),
            "--config",
            str(config),
            "--",
            sys.executable,
            str(stub),
        ],
        env=env,
        capture_output=True,
        text=True,
        cwd=REPO,
        timeout=120,
    )


def test_a_dev_live_run_records_in_lab_folders_named_by_digest_and_round(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    root = tmp_path / "runs"
    config = _write_config(tmp_path / "config")
    stub = _write_stub(tmp_path / "stub_dispatch.py")

    result = _run(home, root, config, stub)

    assert result.returncode == 0, result.stderr
    digest = _digest()
    round_id = _round_id()

    # The row and the reading landed under the lab folder, named by digest and
    # round; the user's default data folder was never touched.
    rows = list(root.rglob("agent-a.jsonl"))
    assert len(rows) == 1
    row_file = rows[0]
    assert root in row_file.parents
    assert digest in str(row_file)
    assert round_id in str(row_file)
    readings = list(root.rglob("reading.json"))
    assert len(readings) == 1
    assert digest in str(readings[0])
    assert round_id in str(readings[0])
    assert not (home / ".local" / "state" / "mcgyvr").exists()

    # tags.json sits beside the recording and names the round and the digest.
    tags = row_file.parent / "tags.json"
    assert tags.is_file()
    doc: Any = json.loads(tags.read_text(encoding="utf-8"))
    assert doc["round"] == round_id
    assert doc["product_digest"] == digest

    # The recording switch is the config's ``journal.dir``, and it names the
    # folder the row landed in. The wrapper moved the data folder and the
    # recording folder, and left MCGYVR_HOME alone (finding 4).
    env_doc: Any = json.loads(
        (readings[0].parent / "env.json").read_text(encoding="utf-8")
    )
    assert env_doc["MCGYVR_HOME"] is None
    assert env_doc["MCGYVR_DATA"] == str(readings[0].parent)
    assert env_doc["MCGYVR_RECORD_DIR"] == str(row_file.parent)
    config_written = Path(env_doc["MCGYVR_CONFIG"])
    assert config_written.is_file()
    merged: Any = yaml.safe_load(config_written.read_text(encoding="utf-8"))
    assert merged["journal"]["dir"] == str(row_file.parent)


def test_the_wrapper_refuses_when_the_recording_folder_cannot_be_set(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    config = _write_config(tmp_path / "config")
    stub = _write_stub(tmp_path / "stub_dispatch.py")
    root = tmp_path / "runs"
    # A file where the wrapper would make the recording folder: the folder the
    # run records into cannot be set, so the run must not start.
    base = root / f"{_round_id()}--{_digest()}"
    base.mkdir(parents=True)
    (base / "journal").write_text("in the way", encoding="utf-8")

    result = _run(home, root, config, stub)

    assert result.returncode != 0
    reasons = [line for line in result.stderr.strip().splitlines() if line.strip()]
    assert len(reasons) == 1
    assert "journal" in reasons[0]


def test_the_wrapper_is_importable_and_exposes_main(tmp_path: Path) -> None:
    module = by_path("live_run", RUN)
    assert callable(module.main)

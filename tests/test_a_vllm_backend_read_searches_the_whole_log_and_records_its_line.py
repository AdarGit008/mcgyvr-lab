# The lab's part of a split test file. The tests of this file that are the
# product's were removed here; they remain in the product's file at this path.
"""A vLLM unit's attention backend is read from its whole log, and the line is kept.

Owner ruling: "fix the reader and record the line". ``rig-id-relock``'s
srv2-03 — a ``read`` of the b-small pair on srv2 — stops with ``STOP srv2-03:
srv2_3b reported no attention_backend`` when both vLLM units file
``attention_backend: null``.

A reader that takes the FIRST line matching ``attention backend`` and looks
for a token in that line alone reads a log that names the backend elsewhere as
``none``. The lock's own method
(``records/measurements/fleet-setup-2026-09-13/srv2/measure_vllm.py``)
searches the WHOLE log for the same tokens, and so does ``rig-units.sh``.

* The backend is the token the whole log carries, over the same token list.
  Owner ruling B4 holds: a backend is never guessed, so a log naming no token
  anywhere stays ``none``.
* The reader also reports what it saw: ``backend_line=PORT,BASE64`` carries the
  first line it matched, truncated, so a ``none`` names the real wording instead
  of nothing. :mod:`mcgyvr.fleet.read` parses it and files it beside
  ``attention_backend`` as data that is never judged.
* The stop stands: ``assemble_evidence.py`` refuses a missing or
  non-unanimous backend.
* srv2-03 is logged as failed, so it gets its one retry. A ``read`` has no
  wrapper and no artifact of its own — its run id is minted when it runs — so
  the retry is the same door command under a new run id.

No rig is reached: every log here is printed by a stub ``docker``, and every
window is written on paper.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

from tests._helpers import PRODUCT
from tests.lockfleets_window import (
    REPO,
    USE,
    WINDOW_DATE,
    Window,
    assemble_module,
    context,
    frozen_window,
    plan_module,
)

STEPS_DIR = REPO / "tools/runs/campaigns/lock-fleets/rig-id-relock"
REASON = "the read filed no attention_backend for either unit"
#: What the repo commits as srv2-03's reason.
SRV2_03_REASON = (
    "both vLLM units filed attention_backend null; the reader read only the "
    "first matching line; owner 2026-09-16: fix the reader and record the line"
)


# --------------------------------------------------------------------------
# the reader on the rig
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# the row, parsed
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# what the read files
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# srv2-03 runs again: a read entry's one retry
# --------------------------------------------------------------------------


def _no_backend(payload: dict[str, Any]) -> None:
    """The srv2-03 defect: both vLLM units filed attention_backend null."""
    for fields in payload["units"].values():
        fields["attention_backend"] = {"observed": None, "attention_backend": None}


def _rig_failed(payload: dict[str, Any]) -> None:
    payload["rig"]["failed"] = {"b_small": "its in-flight page could not be read"}


def _window_to(tmp_path: Path, last: str, change: dict[str, Any]) -> Window:
    window = frozen_window(tmp_path)
    for entry in window.runs.entries:
        window.write(entry, change.get(entry.id))
        if entry.id == last:
            break
    return window


def test_a_read_entry_gets_one_retry_of_its_own_right_after_it(
    tmp_path: Path,
) -> None:
    window = _window_to(tmp_path, "beta-03", {"beta-03": _no_backend})
    plan = plan_module()
    made = plan.retry(window.root, USE, "beta-03", REASON, journal=str(window.journal))
    # A read has no wrapper and no artifact of its own: its run id is minted
    # when it runs, so the retry names neither.
    assert made == {
        "entry": "beta-03",
        "reason": REASON,
        "retry_entry": "beta-03-retry1",
    }
    listed = window.root / "records/measurements/lock-fleets" / USE / "retries.json"
    doc = json.loads(listed.read_text("utf-8"))
    assert doc["retries"] == [made]
    wrappers = window.root / f"tools/runs/campaigns/lock-fleets/{USE}"
    assert not [p for p in wrappers.glob("*.sh") if "beta-03" in p.name]

    runs = plan.read_runs(window.root, USE)
    beta = [e.id for e in runs.entries if e.rig == "beta"]
    assert beta[:5] == ["beta-01", "beta-02", "beta-03", "beta-03-retry1", "beta-04"]
    failed, retry = runs.entry("beta-03"), runs.entry("beta-03-retry1")
    assert (retry.kind, retry.fleet, retry.units, retry.run) == (
        "read",
        "two",
        ("b_small", "b_mid"),
        "c1",
    )
    assert (retry.retry_of, retry.wrapper) == ("beta-03", "")
    # The same door command, under the run id drive.sh mints for it.
    assert retry.argv == failed.argv
    assert retry.artifact == failed.artifact
    assert retry.run_id(WINDOW_DATE, "run-20260916T120000-0a1b2c3d") == (
        "run-20260916T120000-0a1b2c3d"
    )
    assert retry.envelope(WINDOW_DATE) == "journal"
    assert runs.retry_for("beta-03") == retry


def test_a_load_entry_is_retried_the_same_way(tmp_path: Path) -> None:
    """A load is a read of one unit: it starts nothing and mints its own id."""
    window = _window_to(tmp_path, "beta-04", {"beta-04": _rig_failed})
    plan = plan_module()
    made = plan.retry(window.root, USE, "beta-04", REASON, journal=str(window.journal))
    assert made["retry_entry"] == "beta-04-retry1"
    assert "step" not in made and "artifact" not in made
    runs = plan.read_runs(window.root, USE)
    assert runs.entry("beta-04-retry1").kind == "load"


@pytest.mark.parametrize("entry", ["beta-02", "beta-06"], ids=["up", "down"])
def test_retry_refuses_a_serve_entry_that_would_supersede_its_own_file(
    tmp_path: Path, entry: str
) -> None:
    """A second ``serve up``/``serve down`` moves the kept ``serve-<mode>.json``
    aside as superseded, which names a data point superseded."""

    def failed(payload: dict[str, Any]) -> None:
        key = "compose_up_exit" if entry == "beta-02" else "compose_down_exit"
        payload["step"][key] = 1

    window = _window_to(tmp_path, entry, {entry: failed})
    plan = plan_module()
    with pytest.raises(plan.PlanRefusedError, match="only a campaign unit or move"):
        plan.retry(window.root, USE, entry, REASON, journal=str(window.journal))


def test_a_retry_of_a_read_gets_no_extra_of_its_own(tmp_path: Path) -> None:
    window = _window_to(tmp_path, "beta-03", {"beta-03": _no_backend})
    window.retry("beta-03", _no_backend)
    plan = plan_module()
    for give, said in (
        (plan.retry, "beta-03-retry1 is itself a retry"),
        (plan.rerun, "beta-03-retry1 is itself a retry"),
        (plan.diagnose, "only a failed retry of a unit entry"),
        (plan.relaunch, "beta-03-retry1 is not a diagnostic start"),
    ):
        with pytest.raises(plan.PlanRefusedError, match=re.escape(said)):
            give(
                window.root,
                USE,
                "beta-03-retry1",
                REASON,
                journal=str(window.journal),
            )


def test_the_recheck_passes_the_failed_read_and_the_retry_runs_next(
    tmp_path: Path,
) -> None:
    window = _window_to(tmp_path, "beta-03", {"beta-03": _no_backend})
    asm, plan = assemble_module(), plan_module()
    # The stop is the one srv2-03 hit, and it is unchanged.
    before = asm.check(context(window), "beta", "beta-03")
    assert any("b_small reported no attention_backend" in why for why in before)

    plan.retry(window.root, USE, "beta-03", REASON, journal=str(window.journal))
    window.reload()
    ctx = context(window)
    assert asm.check(ctx, "beta", "beta-03") == []
    _reasons, said = asm.verdict(ctx, "beta", "beta-03")
    assert "beta-03 failed, retried by beta-03-retry1" in said
    order = [e.id for e in ctx.runs.entries if e.rig == "beta"]
    unlogged = [e for e in order if ctx.runs.logged(e) is None]
    assert unlogged[0] == "beta-03-retry1"


def test_a_passing_retry_of_a_read_stands_in_for_the_entry_it_retried(
    tmp_path: Path,
) -> None:
    clean = frozen_window(tmp_path / "clean")
    clean.write_all()
    retried = frozen_window(tmp_path / "retried")
    retried.write_all({"beta-03": _no_backend})
    made = retried.retry("beta-03")
    asm = assemble_module()
    want, _, _ = asm.assemble(context(clean))
    evidence, runs, _ = asm.assemble(context(retried))
    assert evidence == want
    kept = runs["runs"]
    assert set(kept) == {e.id for e in retried.runs.entries}
    assert kept["beta-03"]["retried_by"] == made["retry_entry"]
    assert any(
        "reported no attention_backend" in why for why in kept["beta-03"]["check"]
    )
    assert kept["beta-03-retry1"]["retry_of"] == "beta-03"


def test_assembly_refuses_a_failed_read_whose_retry_did_not_pass(
    tmp_path: Path,
) -> None:
    window = frozen_window(tmp_path)
    window.write_all({"beta-03": _no_backend})
    window.retry("beta-03", _no_backend)
    asm = assemble_module()
    with pytest.raises(
        asm.AssemblyRefusedError, match=re.escape("beta-03-retry1 fails its check")
    ):
        asm.assemble(context(window))


# --------------------------------------------------------------------------
# what the repo commits
# --------------------------------------------------------------------------


def test_srv2_03_of_rig_id_relock_has_its_one_retry_committed() -> None:
    plan = plan_module()
    runs = plan.read_runs(REPO, "rig-id-relock")
    srv1 = [e.id for e in runs.entries if e.rig == "srv1"]
    srv2 = [e.id for e in runs.entries if e.rig == "srv2"]
    # srv1 does not move; srv2 gains exactly the read's retry.
    assert (len(srv1), len(srv2)) == (16, 31)
    assert srv2[4:8] == ["srv2-02", "srv2-03", "srv2-03-retry1", "srv2-04"]
    derived, text = plan.derive_retry("rig-id-relock", runs.entry("srv2-03"))
    assert derived == {"retry_entry": "srv2-03-retry1"}
    assert text == ""
    listed = REPO / "records/measurements/lock-fleets/rig-id-relock/retries.json"
    doc = json.loads(listed.read_text("utf-8"))
    assert doc["retries"][-1] == {
        "entry": "srv2-03",
        "reason": SRV2_03_REASON,
        **derived,
    }
    # srv2-01's retry, with its wrapper and artifact, is untouched.
    assert doc["retries"][0]["entry"] == "srv2-01"
    assert len(doc["retries"]) == 2
    assert not [p for p in STEPS_DIR.glob("*.sh") if "srv2-03" in p.name]

    read_entry, retry = runs.entry("srv2-03"), runs.entry("srv2-03-retry1")
    assert retry.retry_of == "srv2-03"
    assert (retry.kind, retry.fleet, retry.units) == (
        "read",
        "b-small",
        ("srv2_3b", "srv2_7b"),
    )
    assert retry.argv == read_entry.argv


def test_the_readme_records_the_2026_09_16_ruling_and_what_it_cites() -> None:
    readme = (REPO / "records/measurements/lock-fleets/README.md").read_text("utf-8")
    assert "2026-09-16" in readme
    assert "srv2-03" in readme
    assert "measure_vllm.py" in readme
    assert "attention_backend" in readme
    # The retry rule does not say only a unit or a move run is retried.
    assert "unit or move run has a wrapper of its own to retry" not in readme
    assert os.access(PRODUCT / "src/mcgyvr/serving/gate-scripts/rig-units.sh", os.R_OK)

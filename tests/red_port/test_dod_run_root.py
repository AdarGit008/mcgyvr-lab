# The lab's copy. The tests of this file that are the product's were removed
# here; they remain in the product's copy of this file.
"""The evidence goes where ``$MCGYVR_RUN_ROOT`` says, and nowhere else.

The door files every run's envelope under ``<root>/records/evidence/``. A root
computed from the door's own file is the repository from a checkout and
``site-packages/`` from an installed wheel, so the root is ``$MCGYVR_RUN_ROOT`` when
that is set.

What must be observably true:

* with ``MCGYVR_RUN_ROOT`` set to an existing directory, the envelope is made
  under it, the gates read their declarations (the round, ``hosts.json``, the
  campaigns) from it, and nothing lands under the checkout the door runs from;
* with it unset, the checkout is the root;
* a value naming a path that is not an existing directory is refused before
  any gate — nothing checked, nothing made, no rig read — and the refusal names
  the variable and the rule. A root the door made silently is how evidence goes
  missing: the operator meant one directory, typed another, and a run filed
  itself where nobody looks.

The serve run is the same door with a second sequence, so the same rule is
stated for it.
"""

from __future__ import annotations

from pathlib import Path

from tests import onedoor

RUN_ROOT_VAR = "MCGYVR_RUN_ROOT"
CAMPAIGN = "root-probe"


def _probe(root: Path, env_file: Path) -> onedoor.Scenario:
    """A campaign step under ``root`` that records the run it was handed."""
    step = onedoor.add_step(root, CAMPAIGN, "1-probe.sh", onedoor.probe_step(env_file))
    return onedoor.Scenario(campaign=CAMPAIGN, step=str(step))


def test_the_envelope_lands_under_the_named_run_root(tmp_path: Path) -> None:
    """The measured case: the door runs from one tree and files under another."""
    checkout = onedoor.fixture_repo(tmp_path / "checkout")
    run_root = onedoor.fixture_repo(tmp_path / "run-root")
    env_file = tmp_path / "env.txt"
    done = onedoor.door(
        checkout,
        _probe(run_root, env_file),
        env_extra={RUN_ROOT_VAR: str(run_root)},
    )
    assert done.returncode == 0, done.stderr[-1500:]

    envelope = onedoor.envelope(run_root, CAMPAIGN)
    assert (envelope / "probe.tsv").is_file(), (
        f"the step's artifact is not under {RUN_ROOT_VAR}={run_root}: "
        f"{onedoor.written_under_records(run_root)}"
    )
    handed = onedoor.read_env_file(env_file)
    assert handed["RUN_OUT_DIR"] == str(envelope), handed
    assert onedoor.written_under_records(checkout) == [], (
        "the checkout the door runs from is not the run root, and got written to"
    )


def test_without_the_variable_the_checkout_is_the_root(tmp_path: Path) -> None:
    """The direction that must not break: nothing named, nothing moves."""
    checkout = onedoor.fixture_repo(tmp_path / "checkout")
    env_file = tmp_path / "env.txt"
    done = onedoor.door(checkout, _probe(checkout, env_file))
    assert done.returncode == 0, done.stderr[-1500:]
    envelope = onedoor.envelope(checkout, CAMPAIGN)
    assert (envelope / "probe.tsv").is_file()
    assert onedoor.read_env_file(env_file)["RUN_OUT_DIR"] == str(envelope)

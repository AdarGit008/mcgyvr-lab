# The lab's copy. The tests of this file that are the product's were removed
# here; they remain in the product's copy of this file.
"""Pattern B — the tree owns the bytes, and one seam commits them.

Pattern B: *"Nothing owns the bytes"* is what happens when several modules
write file content and disagree about where truth lives.
:func:`mcgyvr.deliver.deliver` re-runs the gate over the bytes on disk, inside
the repository lock, immediately before staging, so a caller holding a string
cannot commit it under a verdict reached on something else. A second delivery —
a runner that wrote a carried string into its worktree and committed it itself —
would apply no bar: no re-gate, no digest, no lock. The rule this file holds is
therefore not "carry the bytes more carefully" but:

    The tree is the owner. Content never travels as a value, and one seam
    commits.

``tools/missions/run.py`` delivers through :func:`mcgyvr.deliver.deliver`, handed
the binding minted inside the workspace its gate ran in — the only place it
can be minted, because that sandbox is torn down before the climb returns.

Two of these tests assert the runner's own delivery helpers are gone rather
than driving them. The other two are the guard that stops a second
delivery growing back, and the control that says none of this is merely a
refusal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcgyvr.escalate import Judgement
from mcgyvr.route import Verdict

# --- the second delivery applies no bar -----------------------------------


def test_the_mission_runner_has_no_delivery_of_its_own(
    missions_run: object,
) -> None:
    """The helpers that made the second delivery are gone, by name.

    This test began as a reproduction: it drove ``_files_of`` → ``_place`` →
    ``_commit_delivery`` with the string a caller still held after ``repair``
    rewrote the tree, and watched the rejected bytes reach a commit. Those
    helpers no longer exist, so the reproduction cannot be written — which is the
    outcome, not a gap in the test.

    What replaces it is the narrower claim the reproduction rested on: the runner
    holds no way to write a file into a repository and commit it. ``_place``
    survives and is deliberately not named here — it still writes acceptance
    files into the worktree and the whole-tree sandbox — because writing was
    never the defect. Committing without re-gating was, and
    :func:`test_nothing_but_delivery_commits` is the general form.
    """
    for gone in ("_files_of", "_commit_delivery"):
        assert not hasattr(missions_run, gone), (
            f"`{gone}` is back. It was half of a second delivery implementation "
            f"that wrote `Delivered.value` and committed it without re-running "
            f"the gate; the runner delivers through `mcgyvr.deliver` now."
        )


def test_a_passing_judgement_carries_no_binding_unless_one_was_minted(
    missions_run: object,
) -> None:
    """The default is the refusing direction.

    The runner's delivery branches on ``outcome.judgement.accepted`` and records
    a refusal at stage ``deliver`` when it is ``None`` — the case of a
    caller-supplied ``attempt_for`` that never minted one, which is the old
    defect's exact shape: a passing verdict, and a caller holding bytes nothing
    re-read. That branch is only reachable if a judgement built without a binding
    actually has none, so that is what is pinned here rather than the branch,
    which a full mission run would have to spend a pool to reach.
    """
    assert Judgement(verdict=Verdict.PASSED).accepted is None, (
        "a judgement built without a binding has one, so the runner's `None` "
        "branch can never fire and an unbound climb would be delivered"
    )
    assert missions_run.STAGE_DELIVER == "deliver"  # type: ignore[attr-defined]


# --- one seam commits ------------------------------------------------------


@pytest.fixture
def missions_run() -> object:
    """``tools/missions/run.py``, loaded by path.

    It is a script rather than a package module, and the delivery half of it is
    what this file is about.
    """
    import importlib.util
    import sys

    path = Path(__file__).resolve().parent.parent / "tools" / "missions" / "run.py"
    spec = importlib.util.spec_from_file_location("missions_run_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before execution: the module uses `from __future__ import
    # annotations`, so `@dataclass` resolves its string annotations through
    # `sys.modules[cls.__module__]` and raises on a module that is not there.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

"""A bench workspace is judged as a repository that states no lint configuration.

The bench and the breadth rig measure what the product does for a repository
that states no ruff configuration of its own. The product lints such a
repository by its own default selection, and under that default a deprecated
``typing`` spelling (``from typing import List``, ``List[int]``) is reported and
does not refuse the change. A repository that states its own ruff configuration
is judged as that configuration says, so a workspace the lab stages must state
none, or it measures a different repository from the one it claims to.

The bar a run records for the Python arm is that same default, as the product
states it (``ruff_config_args``), with the rules ruff resolves under it: the
record is read from the product, never restated.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from mcgyvr.gate import Gate, GateResult
from mcgyvr.gate.adapters.python import ruff_config_args
from mcgyvr.gate.changeset import ChangeSet
from mcgyvr.gate.typecheck import STYLE
from mcgyvr.sandbox.tempdir import TempDirSandbox
from tests._helpers import by_path

REPO = Path(__file__).resolve().parent.parent

#: Formatted, import-sorted and correct: the only thing a linter can say about
#: it is the deprecated spelling, on line 1 (UP035) and line 4 (UP006).
OLD_SPELLING = (
    "from typing import List\n"
    "\n"
    "\n"
    "def total(rows: List[int]) -> int:\n"
    '    """Add the rows."""\n'
    "    return sum(rows)\n"
)

#: The codes the old spelling is reported under.
OLD_SPELLING_CODES = {"UP006", "UP035"}

_IDENTITY = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
}


@pytest.fixture(scope="module")
def score() -> Any:
    return by_path("bench_score_noconf", REPO / "tools" / "bench" / "score.py")


@pytest.fixture(scope="module")
def measure() -> Any:
    return by_path("breadth_measure_noconf", REPO / "tools" / "breadth" / "measure.py")


@pytest.fixture(scope="module")
def identity() -> Any:
    return by_path("bench_identity_noconf", REPO / "tools" / "bench" / "identity.py")


@pytest.fixture(scope="module")
def task(measure: Any) -> Any:
    return measure.load_tier_tasks("bench-py", ["b002-option-pairs"])[0]


@contextmanager
def _bare(tmp: Path) -> Iterator[Path]:
    """A repository that states nothing: one empty base commit."""
    subprocess.run(
        ["git", "-C", str(tmp), "init", "-q"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(tmp), "commit", "-q", "--allow-empty", "-m", "base"],
        check=True,
        capture_output=True,
        env={**os.environ, **_IDENTITY},
    )
    yield tmp


def _gated(workspace: Path, target: str, base: str) -> GateResult:
    """The gate's verdict on a change that writes the old spelling to ``target``."""
    (workspace / target).write_text(OLD_SPELLING, encoding="utf-8")
    return Gate().run(ChangeSet.detect(workspace, base))


def _verdict(kind: str, tmp: Path, score: Any, measure: Any, task: Any) -> GateResult:
    """The old spelling, judged in a workspace of ``kind``.

    ``bench`` is the tree ``score.stage_dir`` builds, opened in the sandbox the
    bench scores in; ``breadth`` is the breadth rig's own per-task sandbox;
    ``bare`` is a repository that states nothing.
    """
    target = task.contract.target
    if kind == "bare":
        with _bare(tmp) as workspace:
            return _gated(workspace, target, "HEAD")
    if kind == "bench":
        base = score.stage_dir(task, task.contract.target_content, tmp / "base")
        with TempDirSandbox(base) as sandbox:
            sandbox.reset()
            return _gated(Path(sandbox.workspace), target, sandbox.base_changeset_ref())
    with measure._task_sandbox(task, task.contract, tmp) as sandbox:
        sandbox.reset()
        return _gated(Path(sandbox.workspace), target, sandbox.base_changeset_ref())


@pytest.mark.parametrize("kind", ["bare", "bench", "breadth"])
def test_the_old_spelling_is_noted_and_not_refused(
    kind: str, tmp_path: Path, score: Any, measure: Any, task: Any
) -> None:
    result = _verdict(kind, tmp_path, score, measure, task)

    refused = {f.code for f in result.findings if f.code}
    assert not OLD_SPELLING_CODES & refused, (
        f"a {kind} workspace refused the old spelling, which a repository "
        f"that states no ruff configuration only gets a note for: "
        f"{result.findings}"
    )
    assert result.accepted, f"the {kind} workspace refused: {result.findings}"
    noted = {f.code for f in result.observations if f.check == STYLE}
    assert noted >= OLD_SPELLING_CODES, (
        f"the {kind} workspace did not report the old spelling: {result.observations}"
    )


def _rules_under(args: list[str], workspace: Path) -> list[str]:
    """The rules ruff itself resolves under ``args``: the oracle, asked apart."""
    (workspace / "probe.py").write_text("", encoding="utf-8")
    shown = subprocess.run(
        ["ruff", "check", *args, "--show-settings"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    block = shown.split("linter.rules.enabled = [\n", 1)[1].split("\n]", 1)[0]
    return [line.strip().rstrip(",") for line in block.splitlines()]


@pytest.mark.parametrize("staging", ["bench", "breadth"])
def test_the_recorded_python_bar_is_the_products_default(
    staging: str, score: Any, measure: Any, identity: Any
) -> None:
    stage: Callable[[Path], object] = (
        score.stage_config if staging == "bench" else measure.stage_bar
    )
    with tempfile.TemporaryDirectory() as tmp:
        default = ruff_config_args(Path(tmp))
        rules = _rules_under(default, Path(tmp))
    assert default, "the premise: an empty directory gets the product's default"

    material, why = identity.bar_material(
        rungs=("acceptance",), language="python", stage_workspace=stage
    )

    assert why is None and material is not None, why
    assert material["lint"]["config_source"] == default, (
        "the recorded lint bar is not the product's default for a repository "
        f"that states no ruff configuration: {material['lint']['config_source']!r}"
    )
    assert material["format"]["config_source"] == default
    assert material["lint"]["rules"] == rules
    assert material["lint"]["rules_enabled"] == len(rules)
    bare, why = identity.bar_material(
        rungs=("acceptance",), language="python", stage_workspace=lambda into: None
    )
    assert bare == material, "the bar a staged workspace records is not the bare one"

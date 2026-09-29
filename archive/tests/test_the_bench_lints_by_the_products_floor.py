"""The test that existed only to check ``lint_config``'s copy of the selection.

Archived with ``lint_config`` (``archive/tools/bench/score.py``): the bench no
longer stages a ruff configuration, so there is no staged copy of
``DEFAULT_RUFF_SELECT`` left to drift. The live tests in
``tests/test_the_bench_lints_by_the_products_floor.py`` and
``tests/test_a_bench_workspace_is_judged_as_a_repository_that_states_no_lint_configuration.py``
hold the bench to the product's default. Kept verbatim; nothing runs it.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from mcgyvr.gate.adapters.python import DEFAULT_RUFF_SELECT


def test_the_staged_selection_is_the_products_and_is_not_restated(
    score: Any, tmp_path: Path
) -> None:
    """Weaker than the two above, and kept for one reason: drift.

    ``lint_config`` and ``DEFAULT_RUFF_SELECT`` held the same nine families for
    three days and then quietly stopped. Asserting equality against the imported
    constant is what makes the next narrowing move both at once.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    score.stage_config(workspace)
    staged = tomllib.loads((workspace / "pyproject.toml").read_text(encoding="utf-8"))
    assert staged["tool"]["ruff"]["lint"]["select"] == list(DEFAULT_RUFF_SELECT)

# The lab's part of a split test file. The tests of this file that are the
# product's were removed here; they remain in the product's file at this path.
"""Five checks reach what they are named for.

A check that cannot fail is worse than no check: it occupies the place a real one
would take, and it reports green.

1. **mypy sees ``tools/``.** ``pyproject.toml`` points mypy at ``tools`` under
   ``strict = true``, and does not silence it there.

2. **The package ships ``py.typed``**, so a strict-typed library exports its types.

3. **``docgen.check_reference`` looks a key up under the block it belongs to.**
   ``mode``, ``source``, ``model``, ``enabled``, ``image``, ``dir`` and ``attempts``
   recur across blocks, so a check on the last segment alone would pass on a
   namesake when a whole block stopped rendering.

4. **The always-entries of the door have exactly one name.**

5. **The door's manifest covers every shell reader a gate depends on**,
   ``rig-snapshot.sh`` included, so a missing file is a refusal and not a
   ``FileNotFoundError`` traceback.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_the_type_gate_covers_the_tools_the_makefile_ships() -> None:
    """1. What mypy is pointed at must include what a user is told to run."""
    config = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    mypy = config.get("tool", {}).get("mypy", {})
    files = mypy.get("files", [])
    assert "tools" in files, (
        f"mypy checks {files}; `make journal-index` and `make journal-review` "
        "run tools/live/*.py over the live journal, type-checked by nothing"
    )
    # Pointing mypy at a directory and then silencing it there is the same
    # hole with a longer config. `ignore_errors` on `tools.*` would satisfy the
    # assertion above and check nothing.
    silenced = [
        override
        for override in mypy.get("overrides", [])
        if override.get("ignore_errors")
        and any(
            str(module).startswith("tools")
            for module in (
                override.get("module")
                if isinstance(override.get("module"), list)
                else [override.get("module")]
            )
        )
    ]
    assert not silenced, f"tools/ is listed and then silenced: {silenced}"

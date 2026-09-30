"""``lint_config``, as ``tools/bench/score.py`` carried it until the bench
stopped staging a ruff configuration.

``score.stage_config`` wrote its output into every bench and breadth workspace
as ``pyproject.toml``. Once the product let a repository's own ruff
configuration decide UP006 and UP035 (product pull request 541), that file made
every such workspace a repository with a configuration of its own, and the gate
refused there what it only reports for a repository without one. The bench now
stages no ruff configuration and the product's gate applies its default itself
(``ruff_config_args``). Kept verbatim so the old claim is on the record
(``okf/must-read/always.md``: superseded code is archived, never deleted).
Nothing here is imported by live code.
"""

from __future__ import annotations

from mcgyvr.gate.adapters.python import (
    DEFAULT_RUFF_LINE_LENGTH,
    DEFAULT_RUFF_SELECT,
)


def lint_config() -> str:
    """The product's own lint floor, as a workspace ``pyproject.toml``.

    **Why this file exists.** The staged ``pyproject.toml`` states the
    product's floor (``DEFAULT_RUFF_SELECT``, ``DEFAULT_RUFF_LINE_LENGTH``)
    explicitly, so the bar is a file in the scored workspace and enters
    ``identity.bar_material``; the adapter would apply the same floor through
    :func:`~mcgyvr.gate.adapters.python.ruff_config_args` if it were absent.

    **Why the product's floor and not this repository's ``pyproject.toml``.**
    Stricter than the product is the wrong bar. This repository's selection
    carries rules the product's floor does not (the ``E4``/``E7``/``E9`` note in
    ``src/mcgyvr/gate/adapters/python.py``), so deriving the bench's bar from
    ``pyproject.toml`` would score a reply the product would ship as a lint
    rejection.

    A bench workspace is precisely the case ``DEFAULT_RUFF_SELECT`` is *for* — a
    repository that declares no ruff configuration of its own — so mirroring the
    floor is not an approximation of production, it is production's own answer
    to this exact question. Reading ``pyproject.toml`` instead would measure a
    worker against this repository's house style, which nothing in a bench run
    is about, and would silently move every published pass rate the next time a
    rule is added here for our own prose.

    Imported rather than restated: two copies of a rule list drift. What is
    deliberately *not* carried over from the product's
    :func:`~mcgyvr.gate.adapters.python.ruff_config_args` is ``target-version``:
    it states none, so ruff's default applies there, and stating one here would
    be a bar the product does not apply.
    """
    select = ", ".join(f'"{family}"' for family in DEFAULT_RUFF_SELECT)
    return (
        "[tool.ruff]\n"
        f"line-length = {DEFAULT_RUFF_LINE_LENGTH}\n\n"
        "[tool.ruff.lint]\n"
        f"select = [{select}]\n\n"
        "[tool.ruff.format]\n"
        'quote-style = "double"\n'
        'indent-style = "space"\n'
    )

# The lab's part of a split test file. The tests of this file that are the
# product's were removed here; they remain in the product's file at this path.
"""Draft acceptance is journaled when the server reports it.

The MTP lever's effect is ``timings.draft_n_accepted / draft_n`` on each
completion — how the evidence read acceptance
(``records/evidence/2026-08-28-mtp-ornith/drivers/mtpsweep2.py``). llama-server
puts the two counts on ``timings`` only when it drafted, so a dispatch records
``draft_n`` and ``draft_n_accepted`` on its attempt row when they are reported
and leaves both keys absent otherwise — never zeroed, the rule every token
count in the journal already keeps. A reported zero is a count, and is kept.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _index() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        "live_index_for_draft_counts", REPO / "tools" / "live" / "index.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_journal_index_has_a_column_for_each_count() -> None:
    columns = dict(_index().COLUMNS)
    assert columns.get("draft_n") == "INTEGER"
    assert columns.get("draft_n_accepted") == "INTEGER"

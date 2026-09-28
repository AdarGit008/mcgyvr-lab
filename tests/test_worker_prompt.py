# The lab's copy. The tests of this file that are the product's were removed
# here; they remain in the product's copy of this file.
"""The bundle and the assembled prompt.

Three properties carry the weight here. The shipped Python bundle must *be* the
artifact that was measured, or the numbers describe a different file. The size
ceiling must be enforced by the loader rather than by a comment, since the
measurement says an oversized bundle degrades the worker it is meant to help.
And the assembled prompt must be reachable only through
:meth:`Contract.worker_view`, because the guarantee that orchestrator-only
fields never reach the worker is structural or it is nothing.
"""

from __future__ import annotations

from pathlib import Path

from mcgyvr.contract import Contract, loads
from mcgyvr.worker.bundle import (
    load_bundle,
)

REPO = Path(__file__).resolve().parent.parent
MEASURED_C2 = (
    REPO
    / "records"
    / "evidence"
    / "local-ai-2026-08-02"
    / "data"
    / "context_exp"
    / "bundles"
    / "c2.md"
)


def contract(text: str) -> Contract:
    return loads(text)


# --- the bundle is the measured artifact -----------------------------------


def test_shipped_python_bundle_is_byte_identical_to_the_measured_one() -> None:
    """A reworded bundle is an unmeasured one, whatever it says in the record."""
    shipped = load_bundle("python")
    assert shipped.text.encode("utf-8") == MEASURED_C2.read_bytes()


# --- the ceiling is enforced, not documented -------------------------------


# --- selection reuses the gate's ownership rules ---------------------------


# --- the worker-view boundary ----------------------------------------------


# --- the target's current content ------------------------------------------


# --- the system prompt is the bundle ---------------------------------------


# --- the fit check, check_prompt_fits' first production caller -------------

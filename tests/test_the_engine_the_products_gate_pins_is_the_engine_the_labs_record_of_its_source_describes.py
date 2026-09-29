"""The engine the product's gate pins is the engine the lab's record describes.

The product's semantic check runs a vendored resolver engine only when its
files hash to the digests pinned in ``mcgyvr.gate.semantic`` (``ENGINE_COMMIT``
and ``ENGINE_DIGESTS``). The lab keeps the record of where that engine came
from: its ``MANIFEST.json`` names the upstream commit and the sha256 of every
file taken from it.

Two copies of a hash are two chances to drift. These tests read the pin from
the installed product package and the manifest from the lab's ``records/``,
and hold them equal, so re-pinning the engine is a deliberate act in both
places rather than something a stray edit does quietly in one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcgyvr.gate.semantic import ENGINE_COMMIT, ENGINE_DIGESTS

LAB = Path(__file__).resolve().parents[1]
MANIFEST = LAB / "records" / "evidence" / "ghostcall-2026-08-02" / "MANIFEST.json"
# Where the manifest lists the engine's own files; the pin names them by the
# file name alone, as they sit in the engine's directory.
ENGINE_PREFIX = "src/ghostcall/"


def _manifest() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return loaded


def test_the_record_names_the_commit_the_product_pins() -> None:
    assert _manifest()["source_commit"] == ENGINE_COMMIT


def test_every_pinned_file_has_the_digest_the_record_gives_it() -> None:
    recorded = {
        entry["path"]: entry["sha256"]
        for entry in _manifest()["files"]
        if entry["path"].startswith(ENGINE_PREFIX)
    }
    assert ENGINE_DIGESTS, "the product pins no engine file"
    for name, digest in ENGINE_DIGESTS.items():
        path = ENGINE_PREFIX + name
        assert path in recorded, f"the record lists no {path}"
        assert recorded[path] == digest, path

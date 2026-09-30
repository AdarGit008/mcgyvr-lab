#!/usr/bin/env python3
"""Run a dev-live dispatch from the lab, recording in the lab's own folders.

A product live run keeps no records; a dev-live run, started from the lab,
keeps them (``okf/must-read/the-split.md``). This wrapper is the boundary. It
runs the command named after ``--`` — the dispatch (``mcgyvr run``, the door's
``read``, whatever the caller drives) — with three things set, so the run's
attempts and texts land in the lab's recording folder and its readings and
results land in the lab's data folder, never among live ones in
``~/.local/state/mcgyvr``:

* ``MCGYVR_DATA`` names the lab data folder.
* ``MCGYVR_CONFIG`` names a lab config whose ``journal.dir`` names the lab
  recording folder — today's switch; the config is the caller's, re-written
  with that one key added.
* ``MCGYVR_RECORD_DIR`` names the same recording folder. It is set for the
  readers that will use it after the recording switch moves, and nothing here
  depends on it.

Every folder the run records into names the product digest and the round it ran
under: the two are read once, the digest from the product checkout's git
(``git -C product rev-parse HEAD``) and the round from ``tools/bench/rounds.json``
through ``tools/bench/product.py``, and written into ``tags.json`` beside the
recording. ``MCGYVR_HOME`` is deliberately left alone: the live pointer and the
promoted fleets stay where the owner put them.

The wrapper refuses — one line on stderr, non-zero — when any of these cannot
be set: no product digest, no open round, a config it cannot read, a folder it
cannot make or write, no dispatch named.

Usage::

    uv run --no-sync python tools/live/run.py --root DIR [--config PATH] \
        -- DISPATCH [ARGS...]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import types
from dataclasses import replace
from pathlib import Path

from mcgyvr import config as configlib

#: The lab checkout this file lives in (tools/live/run.py -> the lab's root).
LAB = Path(__file__).resolve().parents[2]
#: The product checkout, a submodule: where the digest is read from.
PRODUCT = LAB / "product"
#: The ``sys.modules`` slot ``tools/bench/product.py`` is loaded into — the one
#: every reader that reaches it by path uses, so there is one copy per process.
BENCH_PRODUCT_SLOT = "bench_product"

#: The names a run's folders carry, so a folder says what it is.
RUN_CONFIG_NAME = "mcgyvr.yaml"
TAGS_NAME = "tags.json"
RECORD_NAME = "journal"
DATA_NAME = "data"
CONFIG_DIR_NAME = "config"


class RefusedError(Exception):
    """The wrapper cannot start: the one-line reason it will print."""


def _bench_product() -> types.ModuleType:
    """``tools/bench/product.py`` by path, through the shared module slot."""
    cached = sys.modules.get(BENCH_PRODUCT_SLOT)
    if cached is not None:
        return cached
    path = LAB / "tools" / "bench" / "product.py"
    spec = importlib.util.spec_from_file_location(BENCH_PRODUCT_SLOT, path)
    if spec is None or spec.loader is None:
        raise RefusedError(
            f"dev-live: {path} cannot be loaded, so the open round cannot be read"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def product_digest(product_dir: Path = PRODUCT) -> str:
    """The product checkout's HEAD, or a refusal naming why it is unavailable."""
    done = subprocess.run(
        ["git", "-C", str(product_dir), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        reason = " ".join(done.stderr.strip().split()) or "git rev-parse HEAD failed"
        raise RefusedError(f"dev-live: no product digest: {reason}")
    digest = done.stdout.strip()
    if not digest:
        raise RefusedError("dev-live: no product digest: git rev-parse HEAD named none")
    return digest


def open_round_id() -> str:
    """The round now accepting measurements, or a refusal naming why none reads."""
    try:
        return str(_bench_product().open_round()["id"])
    except RefusedError:
        raise
    except Exception as exc:  # a missing or unreadable rounds.json is a refusal
        raise RefusedError(f"dev-live: the open round cannot be read: {exc}") from exc


def run_folders(
    root: Path, round_id: str, digest: str
) -> tuple[Path, Path, Path, Path]:
    """``(base, record, data, config)`` under ``root``, named by round and digest.

    One base folder per run: ``<round>--<digest>``. The recording folder
    (``journal/``), the data folder (``data/``) and the config folder
    (``config/``) sit under it, so every folder the run records into carries
    the round and the digest it ran under.
    """
    base = root / f"{round_id}--{digest}"
    return (
        base,
        base / RECORD_NAME,
        base / DATA_NAME,
        base / CONFIG_DIR_NAME,
    )


def _merged_config_text(source: Path | None, record_dir: Path) -> str:
    """The caller's config as one document, with ``journal.dir`` added.

    The recording switch is the config's ``journal.dir``; this wrapper adds
    that one key to the config the run would otherwise use, and nothing else —
    the units, ladder and profile are the caller's. Rendered through the
    product's own ``Config.canonical`` so the copy is the config, byte for
    byte, plus the one key.
    """
    try:
        loaded = configlib.load(source)
    except configlib.ConfigError as exc:
        raise RefusedError(f"dev-live: the config cannot be read: {exc}") from exc
    data = {
        **loaded.data,
        "journal": {**loaded.data.get("journal", {}), "dir": str(record_dir)},
    }
    declared = {
        **loaded.declared,
        "journal": {**loaded.declared.get("journal", {}), "dir": str(record_dir)},
    }
    merged = replace(loaded, data=data, declared=declared)
    try:
        return merged.canonical()
    except Exception as exc:
        raise RefusedError(f"dev-live: the config cannot be rendered: {exc}") from exc


def _make(path: Path, what: str) -> None:
    """Make ``path``, or refuse with a one-line reason naming it."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        why = " ".join(str(exc).split())
        raise RefusedError(f"dev-live: {what} {path} cannot be made: {why}") from exc


def _parse(argv: list[str]) -> tuple[Path, Path | None, list[str]]:
    """The wrapper's flags and the dispatch, split at ``--``."""
    if "--" in argv:
        cut = argv.index("--")
        flags, dispatch = argv[:cut], argv[cut + 1 :]
    else:
        flags, dispatch = argv, []
    parser = argparse.ArgumentParser(
        prog="tools/live/run.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--root",
        required=True,
        type=Path,
        help="where this run's lab folders are made, by an absolute path",
    )
    parser.add_argument(
        "--config",
        default=None,
        type=Path,
        help=(
            "the config to copy with journal.dir added (default: "
            "$MCGYVR_CONFIG, else the located config)"
        ),
    )
    opts = parser.parse_args(flags)
    return opts.root, opts.config, dispatch


def _run(argv: list[str]) -> int:
    root, config, dispatch = _parse(argv)
    if not root.is_absolute():
        raise RefusedError(
            f"dev-live: --root {root!r} is not an absolute path; name the lab "
            "folder by an absolute path"
        )
    if not dispatch:
        raise RefusedError("dev-live: no dispatch named after --; nothing to run")

    digest = product_digest()
    round_id = open_round_id()
    base, record, data, config_dir = run_folders(root, round_id, digest)

    # The config is read and re-written before any folder is made, so a config
    # that cannot be read leaves nothing behind.
    config_text = _merged_config_text(config, record)

    _make(base, "the run folder")
    _make(record, "the recording folder")
    _make(data, "the data folder")
    _make(config_dir, "the config folder")

    config_file = config_dir / RUN_CONFIG_NAME
    try:
        config_file.write_text(config_text, encoding="utf-8")
    except OSError as exc:
        raise RefusedError(
            f"dev-live: the config {config_file} cannot be written: {exc}"
        ) from exc
    try:
        (record / TAGS_NAME).write_text(
            json.dumps({"round": round_id, "product_digest": digest}) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise RefusedError(
            f"dev-live: the tags file beside the recording cannot be written: {exc}"
        ) from exc

    env = dict(os.environ)
    env["MCGYVR_DATA"] = str(data)
    env["MCGYVR_CONFIG"] = str(config_file)
    env["MCGYVR_RECORD_DIR"] = str(record)
    # MCGYVR_HOME is deliberately not set: the live pointer and the promoted
    # fleets stay in the config folder, where the owner put them.
    try:
        os.execvpe(dispatch[0], dispatch, env)
    except OSError as exc:
        raise RefusedError(
            f"dev-live: the dispatch {dispatch[0]!r} cannot be run: {exc}"
        ) from exc
    return 0  # unreachable: exec replaces this process with the dispatch


def main(argv: list[str] | None = None) -> int:
    given = list(sys.argv[1:] if argv is None else argv)
    try:
        return _run(given)
    except RefusedError as refused:
        print(str(refused), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

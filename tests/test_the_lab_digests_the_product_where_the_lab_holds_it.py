"""The lab's ``tools/bench/product.py`` digests the product where the lab holds it.

In the product's checkout every entry of ``SURFACE`` sits under one root. In
the lab the rig files (``tools/...``) are the lab's own, at the lab's root,
and the product is the submodule at ``product/``: ``src/mcgyvr``, the lint and
lock files and ``data/task-catalog.json`` are there. Gate 1 loads
``<run root>/tools/bench/product.py`` and calls ``ensure_open()`` with the
module's own root, so with the lab as the run root the digest has to be
taken over that split layout, or gate 1 refuses every run started from the
lab.

The promise kept: the same files give the same digest, whether they are laid
out as the product's checkout or as the lab, and whether the lab's module or
the product's module takes it. Rounds recorded so far stay comparable.
"""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import types
from pathlib import Path

from tests._helpers import PRODUCT

LAB = Path(__file__).resolve().parent.parent
LAB_MODULE = LAB / "tools" / "bench" / "product.py"
PRODUCT_MODULE = PRODUCT / "tools" / "bench" / "product.py"


def _load(name: str, path: Path) -> types.ModuleType:
    """A fresh copy of a module, in no shared ``sys.modules`` slot."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _trees(tmp_path: Path, surface: tuple[str, ...]) -> tuple[Path, Path]:
    """One set of files, laid out as the product's checkout and as the lab."""
    flat = tmp_path / "product-shaped"
    lab = tmp_path / "lab-shaped"
    files: dict[str, str] = {}
    for entry in surface:
        if entry == "src/mcgyvr":
            files["src/mcgyvr/__init__.py"] = "x = 1\n"
            files["src/mcgyvr/prompts/python.md"] = "You are a worker.\n"
        elif entry == "tools/bench/product.py":
            files[entry] = LAB_MODULE.read_text(encoding="utf-8")
        else:
            files[entry] = f"# {entry}\n"
    for rel, text in files.items():
        _write(flat, rel, text)
        _write(lab if rel.startswith("tools/") else lab / "product", rel, text)
    # What else sits at a lab's root is not the product's and is not read.
    _write(lab, "pyproject.toml", "[project]\nname = 'the-lab'\n")
    _write(lab, "uv.lock", "the lab's lock\n")
    return flat, lab


def test_the_labs_own_tree_is_digested() -> None:
    lab = _load("lab_bench_product", LAB_MODULE)
    assert len(lab.digest()) == 64


def test_one_set_of_files_has_one_digest_in_either_layout_and_either_module(
    tmp_path: Path,
) -> None:
    lab = _load("lab_bench_product", LAB_MODULE)
    product = _load("product_bench_product", PRODUCT_MODULE)
    assert lab.SURFACE == product.SURFACE
    flat, lab_shaped = _trees(tmp_path, lab.SURFACE)

    by_the_product = product.digest(flat)
    assert lab.digest(flat) == by_the_product
    assert lab.digest(lab_shaped) == by_the_product
    assert list(lab._lines(lab_shaped)) == list(product._lines(flat))


def test_the_product_half_of_the_labs_digest_is_the_submodules_files() -> None:
    lab = _load("lab_bench_product", LAB_MODULE)
    lines = dict(line.split(" ") for line in lab._lines(LAB))
    product_side = {k: v for k, v in lines.items() if not k.startswith("tools/")}
    assert product_side, "no product file was digested"
    for rel, sha in product_side.items():
        assert hashlib.sha256((PRODUCT / rel).read_bytes()).hexdigest() == sha, rel
    for rel in (k for k in lines if k.startswith("tools/")):
        assert hashlib.sha256((LAB / rel).read_bytes()).hexdigest() == lines[rel], rel


def test_a_lab_without_its_product_is_refused_by_name(tmp_path: Path) -> None:
    lab = _load("lab_bench_product", LAB_MODULE)
    _, lab_shaped = _trees(tmp_path, lab.SURFACE)
    shutil.rmtree(lab_shaped / "product" / "src")
    try:
        lab.digest(lab_shaped)
    except lab.ProductError as error:
        assert "src/mcgyvr" in str(error)
    else:
        raise AssertionError("a surface entry that is missing was not refused")


def test_a_lab_whose_product_folder_is_empty_is_refused(tmp_path: Path) -> None:
    """An uninitialised submodule is an empty ``product/``: nothing to digest."""
    lab = _load("lab_bench_product", LAB_MODULE)
    _, lab_shaped = _trees(tmp_path, lab.SURFACE)
    shutil.rmtree(lab_shaped / "product")
    (lab_shaped / "product").mkdir()
    try:
        lab.digest(lab_shaped)
    except lab.ProductError:
        pass
    else:
        raise AssertionError("an empty product/ was digested, not refused")

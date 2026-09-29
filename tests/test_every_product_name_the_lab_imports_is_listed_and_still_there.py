"""Every product name the lab's own code imports is listed here and is still there.

The lab's gates, tools and tests import names from the product it installs. A
product change that removes or renames one of them breaks the lab file that
uses it, and the rest of the lab's gate does not read every such file: no lint
or type check reads a shell file or a script kept under ``fleet-setup/``, and a
test reaches such a line only if it happens to run it. So each name is listed
below with one lab file that uses it, and each is looked up in the installed
product by that name.

The list is the set the lab uses, no more and no less. A scan of the lab's own
files finds every product name they import; a name the scan finds that the
list lacks fails, and so does a listed name the scan no longer finds in the
file the list gives for it.

What the scan counts as importing a name, in a Python file: ``from mcgyvr.x
import y``; ``import mcgyvr.x``; an attribute read off a name bound to
something of the product, also after ``w = z``; and ``(z, "y")`` given to
``getattr``, ``setattr``, ``hasattr``, ``delattr`` or ``patch.object``, or
written as a pair. In a shell file or a Makefile: ``from mcgyvr.x import y``,
``import mcgyvr.x`` and ``-m mcgyvr.x``. A name is the one the product's
module holds; a submodule is a name of its package, and an attribute of a
class counts as its class. The lab's own files are every ``.py``, ``.sh`` and
``Makefile`` outside ``product/``, ``records/``, ``archive/``, hidden folders,
``__pycache__`` and ``node_modules``.
"""

from __future__ import annotations

import ast
import functools
import importlib
import importlib.util
import os
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parents[1]

#: The lab's top folders that hold no code of the lab's own to scan: the
#: product itself, and the records and retired code kept as they were.
NOT_SCANNED = frozenset({"product", "records", "archive"})

#: One line per name: the product module, the name the lab imports from it,
#: and one lab file that imports it (outside ``tests/`` when one does).
LISTED = """
mcgyvr                        config                   tests/test_a_locked_fleet_loads_as_the_run_config.py
mcgyvr                        contract                 tests/test_bundle_ladder.py
mcgyvr                        derived                  tests/lab_numbers.py
mcgyvr                        drive                    tests/livejournal.py
mcgyvr                        runner                   tests/conftest.py
mcgyvr                        scan                     tests/test_a_locked_fleet_emits_its_hashed_launch.py
mcgyvr                        telemetry                tests/test_a_live_row_names_what_answered_it_and_under_which_round.py
mcgyvr.catalog                Family                   tools/missions/attempt.py
mcgyvr.catalog                catalog                  tools/missions/run.py
mcgyvr.cli                    main                     tests/livejournal.py
mcgyvr.config                 Config                   tools/missions/run.py
mcgyvr.config                 _split_setup             tests/_helpers.py
mcgyvr.config                 load                     tools/missions/run.py
mcgyvr.config                 parse                    tests/test_a_locked_fleet_loads_as_the_run_config.py
mcgyvr.contract               Contract                 tools/bench/admit.py
mcgyvr.contract               ContractError            tools/bench/admit.py
mcgyvr.contract               dumps                    tools/bundle/measure.py
mcgyvr.contract               load                     tools/bench/admit.py
mcgyvr.contract               loads                    tests/red_port/conftest.py
mcgyvr.deliver                Accepted                 tools/missions/attempt.py
mcgyvr.deliver                DeliveryError            tools/missions/run.py
mcgyvr.deliver                Identity                 tools/missions/run.py
mcgyvr.deliver                deliver                  tools/missions/run.py
mcgyvr.deliver                digest_of                tests/test_fix_mission_readback_bytes.py
mcgyvr.derived                CLASS_PCT_ENTRIES        tests/lab_numbers.py
mcgyvr.derived                RUNTIME_RESIDENT         tests/lab_numbers.py
mcgyvr.derived                RUNTIME_RESIDENT_KEY     tests/lab_numbers.py
mcgyvr.derived                class_tolerance_numbers  tests/lab_numbers.py
mcgyvr.derived                lookup                   tests/test_derived_numbers.py
mcgyvr.derived                overrides_path           tests/lab_numbers.py
mcgyvr.derived                runtime_resident_gb      tests/test_derived_numbers.py
mcgyvr.drive                  _in_order                tests/livejournal.py
mcgyvr.drive                  dispatch                 tests/livejournal.py
mcgyvr.drive                  run_batch                tests/livejournal.py
mcgyvr.emit                   emit_locked              tools/runs/campaigns/lock-fleets/lockfleets.py
mcgyvr.escalate               Assurance                tests/test_fix_mission_readback_bytes.py
mcgyvr.escalate               Delivered                tools/missions/run.py
mcgyvr.escalate               Halted                   tools/missions/run.py
mcgyvr.escalate               Judgement                tools/missions/attempt.py
mcgyvr.escalate               RetryNotes               tools/missions/attempt.py
mcgyvr.escalate               escalate                 tools/missions/run.py
mcgyvr.escalate               judge                    tools/missions/attempt.py
mcgyvr.exits                  Exit                     tests/test_a_locked_fleet_emits_its_hashed_launch.py
mcgyvr.fleet                  alerts                   tests/test_a_live_probe_is_judged_against_its_lock.py
mcgyvr.fleet                  harness                  tools/runs/campaigns/lock-fleets/lockfleets.py
mcgyvr.fleet                  lock                     tests/test_a_live_probe_is_judged_against_its_lock.py
mcgyvr.fleet                  probe                    tests/test_a_live_probe_is_judged_against_its_lock.py
mcgyvr.fleet                  read                     tests/conftest.py
mcgyvr.fleet.alerts           check                    tests/test_a_live_probe_is_judged_against_its_lock.py
mcgyvr.fleet.files            FleetFileError           tools/runs/campaigns/lock-fleets/lockfleets.py
mcgyvr.fleet.files            load_fleet               tools/runs/campaigns/lock-fleets/lockfleets.py
mcgyvr.fleet.files            load_policy              tests/test_lock_fleets_assembles_only_what_its_runs_prove.py
mcgyvr.fleet.harness          HARNESS_WORD             tools/runs/campaigns/lock-fleets/lockfleets.py
mcgyvr.fleet.harness          __file__                 tools/runs/campaigns/lock-fleets/lockfleets.py
mcgyvr.fleet.ids              digest                   fleet-setup/digests-srv1.json.py
mcgyvr.fleet.ids              rig_id                   tests/lockfleets_window.py
mcgyvr.fleet.layout           AWAKE                    tools/runs/campaigns/lock-fleets/lockfleets.py
mcgyvr.fleet.lock             _combination_id_for      tests/test_lock_fleets_assembles_only_what_its_runs_prove.py
mcgyvr.fleet.lock             _switch_moves            tools/runs/campaigns/lock-fleets/lockfleets.py
mcgyvr.fleet.lock             write                    tests/test_a_live_probe_is_judged_against_its_lock.py
mcgyvr.fleet.probe            run                      tests/test_a_live_probe_is_judged_against_its_lock.py
mcgyvr.fleet.read             _pace_counter            tools/runs/campaigns/lock-fleets/lockfleets.py
mcgyvr.fleet.read             spawn_read               tests/conftest.py
mcgyvr.fleet.tolerance        CLASS_CPU_EXPERTS        tests/test_a_unit_that_drafts_with_its_own_head_is_judged_by_its_own_class.py
mcgyvr.fleet.tolerance        CLASS_MTP                tests/test_a_unit_that_drafts_with_its_own_head_is_judged_by_its_own_class.py
mcgyvr.fleet.tolerance        tolerance_class          tests/test_a_unit_that_drafts_with_its_own_head_is_judged_by_its_own_class.py
mcgyvr.gate                   Acceptance               tools/missions/attempt.py
mcgyvr.gate                   ChangeSet                tools/missions/attempt.py
mcgyvr.gate                   Gate                     tools/missions/attempt.py
mcgyvr.gate                   GateResult               tools/missions/attempt.py
mcgyvr.gate                   LanguageAdapter          tools/missions/attempt.py
mcgyvr.gate.acceptance        Acceptance               tools/bench/score.py
mcgyvr.gate.adapters          JavaScriptAdapter        tools/bench/identity.py
mcgyvr.gate.adapters          PythonAdapter            tools/bench/identity.py
mcgyvr.gate.adapters.python   DEFAULT_RUFF_LINE_LENGTH tools/bench/score.py
mcgyvr.gate.adapters.python   DEFAULT_RUFF_SELECT      tools/bench/score.py
mcgyvr.gate.changeset         ChangeSet                tools/bench/score.py
mcgyvr.gate.preflight         check_prompt_fits        tools/breadth/measure.py
mcgyvr.gate.runner            Gate                     tools/bench/lintless.py
mcgyvr.gate.semantic          ENGINE_COMMIT            tests/test_the_engine_the_products_gate_pins_is_the_engine_the_labs_record_of_its_source_describes.py
mcgyvr.gate.semantic          ENGINE_DIGESTS           tests/test_the_engine_the_products_gate_pins_is_the_engine_the_labs_record_of_its_source_describes.py
mcgyvr.orchestrator.decompose Decomposition            tools/missions/run.py
mcgyvr.orchestrator.decompose DepRef                   tools/missions/propose.py
mcgyvr.orchestrator.decompose Evidence                 tools/missions/propose.py
mcgyvr.orchestrator.decompose Proposal                 tools/missions/propose.py
mcgyvr.orchestrator.decompose Proposer                 tools/missions/run.py
mcgyvr.orchestrator.decompose RecordedProposer         tools/tokens/measure.py
mcgyvr.orchestrator.decompose Refusal                  tools/missions/propose.py
mcgyvr.orchestrator.decompose decompose                tools/missions/run.py
mcgyvr.orchestrator.index     Index                    tools/missions/run.py
mcgyvr.orchestrator.index     build_index              tools/missions/run.py
mcgyvr.orchestrator.read      estimate_tokens          tools/breadth/measure.py
mcgyvr.orchestrator.read      explore                  tools/tokens/measure.py
mcgyvr.orchestrator.repo      attach                   tools/missions/run.py
mcgyvr.orchestrator.resolve   resolve                  tools/tokens/measure.py
mcgyvr.orchestrator.symbols   SymbolKind               tools/tokens/measure.py
mcgyvr.pool                   Endpoint                 tools/bundle/measure.py
mcgyvr.pool                   PoolError                tools/missions/run.py
mcgyvr.pool                   Protocol                 tools/bundle/measure.py
mcgyvr.pool                   SourceMap                tools/missions/attempt.py
mcgyvr.pool                   source_map               tools/missions/run.py
mcgyvr.route                  Try                      tools/missions/attempt.py
mcgyvr.route                  Verdict                  tools/missions/attempt.py
mcgyvr.route                  family_of                tools/missions/run.py
mcgyvr.runner                 Completion               tools/missions/attempt.py
mcgyvr.runner                 Request                  tools/breadth/measure.py
mcgyvr.runner                 RunnerError              tools/breadth/measure.py
mcgyvr.runner                 StopReason               tools/bench/gate_rescore.py
mcgyvr.runner                 TransportError           tests/test_bundle_ladder.py
mcgyvr.runner                 _get_text                tests/conftest.py
mcgyvr.runner                 dispatch                 tools/missions/attempt.py
mcgyvr.runner                 runner_for               tools/breadth/measure.py
mcgyvr.sandbox.base           CommandResult            tools/missions/attempt.py
mcgyvr.sandbox.base           Sandbox                  tools/missions/attempt.py
mcgyvr.sandbox.tempdir        TempDirSandbox           tools/bench/gate_rescore.py
mcgyvr.scan                   SCAN_ROOT_ENV            tests/test_a_locked_fleet_emits_its_hashed_launch.py
mcgyvr.scope                  Scope                    tests/test_bench_gate_rescore.py
mcgyvr.serving                gatelib                  tools/runs/drivers/lcp_sweep.py
mcgyvr.serving                ggufscan                 tools/bench/serving/backends/llamacpp.py
mcgyvr.serving                run                      tools/runs/_common.sh
mcgyvr.serving                spec_name                tools/runs/campaigns/lock-fleets/lockfleets.py
mcgyvr.serving                vramfit                  tools/bench/serving/backends/llamacpp.py
mcgyvr.serving.gatelib        door_required            tools/runs/drivers/lcp_sweep.py
mcgyvr.serving.gatelib        envelope_escape          tools/runs/campaigns/lock-fleets/lockfleets.py
mcgyvr.serving.gatelib        ssh                      tools/bench/serving/contract.py
mcgyvr.serving.gatelib        ssh_spends               tests/test_lock_fleets_steps_start_only_what_fleet_yaml_names.py
mcgyvr.serving.gatelib        under_door               tools/runs/_common.sh
mcgyvr.serving.ggufscan       __file__                 tools/bench/serving/backends/llamacpp.py
mcgyvr.serving.run            DEFAULT_STEP             tests/test_serving_door_cli.py
mcgyvr.serving.run            EXPORTED                 tests/test_one_door.py
mcgyvr.serving.run            ROOT                     tests/test_serving_door_cli.py
mcgyvr.serving.run            ROOT_ENV                 tests/test_serving_door_cli.py
mcgyvr.serving.run            _check_step_args         tests/test_serving_door_cli.py
mcgyvr.serving.servelib       ComposeError             tools/runs/campaigns/lock-fleets/lockfleets.py
mcgyvr.serving.servelib       PROJECT                  tools/runs/campaigns/lock-fleets/lockfleets.py
mcgyvr.serving.servelib       services                 tools/runs/campaigns/lock-fleets/lockfleets.py
mcgyvr.serving.vramfit        SCRATCH_AND_CONTEXT_MIB  tools/bench/serving/backends/llamacpp.py
mcgyvr.serving.vramfit        experts_on_card          tools/bench/serving/backends/llamacpp.py
mcgyvr.serving.vramfit        floor                    tools/bench/serving/backends/llamacpp.py
mcgyvr.serving.vramfit        kv_bytes                 tools/bench/serving/backends/llamacpp.py
mcgyvr.serving.vramfit        rs_bytes                 tools/bench/serving/backends/llamacpp.py
mcgyvr.telemetry              ATTEMPT_KIND             tools/live/index.py
mcgyvr.telemetry              BLOB_DIR                 tools/live/index.py
mcgyvr.telemetry              CORRECTION_KIND          tests/_helpers.py
mcgyvr.telemetry              STOCK                    tools/breadth/measure.py
mcgyvr.telemetry              _product_revision        tests/test_a_live_row_names_what_answered_it_and_under_which_round.py
mcgyvr.telemetry              correct                  tests/test_a_review_prints_the_prompt_the_reply_and_how_it_landed.py
mcgyvr.telemetry              fold                     tools/live/index.py
mcgyvr.telemetry              observe                  tests/test_a_live_row_names_what_answered_it_and_under_which_round.py
mcgyvr.worker.bundle          BundleStanding           tests/test_bundle_ladder.py
mcgyvr.worker.bundle          MAX_BUNDLE_BYTES         tests/test_bundle_ladder.py
mcgyvr.worker.bundle          bundle_for               tools/bundle/measure.py
mcgyvr.worker.bundle          load_bundle              tests/test_worker_prompt.py
mcgyvr.worker.bundle          strip_provenance         tests/test_bundle_ladder.py
mcgyvr.worker.prompt          build_prompt             tools/breadth/measure.py
mcgyvr.worker.prompt          render_user_message      tools/bundle/measure.py
mcgyvr.worker.reply           ParsedFile               tools/missions/attempt.py
mcgyvr.worker.reply           ReplyError               tools/bench/gate_rescore.py
mcgyvr.worker.reply           WHOLE_FILE               tools/replies/pin.py
mcgyvr.worker.reply           parse_reply              tools/bench/gate_rescore.py
"""  # noqa: E501

SHELL_FROM = re.compile(r"\bfrom\s+(mcgyvr(?:\.\w+)*)\s+import\s+([\w ,]+)")
SHELL_MODULE = re.compile(r"(?:\bimport|(?<!\S)-m)\s+(mcgyvr(?:\.\w+)*)")
PAIR_CALLS = frozenset({"getattr", "setattr", "hasattr", "delattr", "object"})


def _is_product(dotted: str) -> bool:
    return dotted.startswith("mcgyvr.")


def _lab_files() -> Iterator[Path]:
    """The lab's own code files that name the product."""
    for folder, subfolders, files in os.walk(LAB):
        top = Path(folder) == LAB
        subfolders[:] = sorted(
            name
            for name in subfolders
            if not name.startswith(".")
            and name not in {"__pycache__", "node_modules"}
            and not (top and name in NOT_SCANNED)
        )
        for name in sorted(files):
            path = Path(folder) / name
            if path.suffix in {".py", ".sh"} or name == "Makefile":
                yield path


def _in_shell(text: str) -> Iterator[str]:
    for line in text.splitlines():
        for found in SHELL_FROM.finditer(line):
            for item in found.group(2).split(","):
                words = item.split()
                if words:
                    yield f"{found.group(1)}.{words[0]}"
        for found in SHELL_MODULE.finditer(line):
            yield found.group(1)


def _chain(node: ast.expr, bound: dict[str, str]) -> str | None:
    """``z.a.b`` spelled out from what ``z`` is bound to, or None."""
    names: list[str] = []
    while isinstance(node, ast.Attribute):
        names.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name) and node.id in bound:
        return ".".join([bound[node.id], *reversed(names)])
    return None


def _in_python(text: str) -> Iterator[str]:
    nodes = list(ast.walk(ast.parse(text)))
    bound: dict[str, str] = {}
    for node in nodes:
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module == "mcgyvr" or _is_product(node.module):
                for alias in node.names:
                    dotted = f"{node.module}.{alias.name}"
                    yield dotted
                    bound[alias.asname or alias.name] = dotted
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _is_product(alias.name):
                    yield alias.name
                    if alias.asname:
                        bound[alias.asname] = alias.name
                    else:
                        bound["mcgyvr"] = "mcgyvr"
    renames = [
        (node.targets[0].id, node.value.id)
        for node in nodes
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Name)
    ]
    rebound = True
    while rebound:
        rebound = False
        for new, old in renames:
            if old in bound and new not in bound:
                bound[new] = bound[old]
                rebound = True
    for node in nodes:
        if isinstance(node, ast.Attribute):
            read = _chain(node, bound)
            if read is not None:
                yield read
        pair: tuple[ast.expr, ast.expr] | None = None
        if isinstance(node, ast.Call) and len(node.args) >= 2:
            func = node.func
            called = (
                func.id
                if isinstance(func, ast.Name)
                else func.attr
                if isinstance(func, ast.Attribute)
                else None
            )
            if called in PAIR_CALLS:
                pair = (node.args[0], node.args[1])
        elif isinstance(node, ast.Tuple) and len(node.elts) == 2:
            pair = (node.elts[0], node.elts[1])
        if pair is not None:
            owner, attribute = pair
            read = _chain(owner, bound)
            if (
                read is not None
                and isinstance(attribute, ast.Constant)
                and isinstance(attribute.value, str)
            ):
                yield f"{read}.{attribute.value}"


@functools.cache
def _name_of(dotted: str) -> tuple[str, str]:
    """The product module and the name in it that ``dotted`` reaches.

    The module is the longest part of ``dotted`` that imports; the name is the
    next part. When all of ``dotted`` imports, it is a name of its package.
    """
    parts = dotted.split(".")
    for cut in range(len(parts), 0, -1):
        module = ".".join(parts[:cut])
        try:
            importlib.import_module(module)
        except ImportError:
            continue
        if cut == len(parts):
            parent, _, leaf = module.rpartition(".")
            return parent, leaf
        return module, parts[cut]
    return parts[0], parts[1]


@functools.cache
def _scan() -> dict[tuple[str, str], frozenset[str]]:
    """Each product name the lab's own files import, and the files that do."""
    found: dict[tuple[str, str], set[str]] = {}
    for path in _lab_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        if "mcgyvr" not in text:
            continue
        spelled = _in_python(text) if path.suffix == ".py" else _in_shell(text)
        where = path.relative_to(LAB).as_posix()
        for dotted in spelled:
            if _is_product(dotted):
                found.setdefault(_name_of(dotted), set()).add(where)
    return {key: frozenset(files) for key, files in found.items()}


def _one(files: frozenset[str]) -> str:
    """The file a line names: a file outside ``tests/`` when one imports it."""
    return min(files, key=lambda where: (where.startswith("tests/"), where))


def _listed() -> list[tuple[str, str, str]]:
    rows = []
    for line in LISTED.strip().splitlines():
        module, name, where = line.split()
        rows.append((module, name, where))
    return rows


@pytest.mark.parametrize(
    ("module", "name", "where"),
    _listed(),
    ids=[f"{module}.{name}" for module, name, _ in _listed()],
)
def test_a_name_the_lab_imports_is_still_in_the_product(
    module: str, name: str, where: str
) -> None:
    try:
        loaded = importlib.import_module(module)
    except ModuleNotFoundError:
        pytest.fail(f"{module} is gone from the product; {where} imports {name}")
    there = hasattr(loaded, name) or (
        hasattr(loaded, "__path__")
        and importlib.util.find_spec(f"{module}.{name}") is not None
    )
    assert there, f"{module}.{name} is gone from the product; {where} imports it"


def test_every_product_name_the_lab_imports_is_listed() -> None:
    listed = {(module, name) for module, name, _ in _listed()}
    missing = [
        f"{module} {name} {_one(files)}"
        for (module, name), files in sorted(_scan().items())
        if (module, name) not in listed
    ]
    assert not missing, (
        "the lab imports these product names and the list lacks them "
        "(module, name, one file):\n" + "\n".join(missing)
    )


def test_every_listed_name_is_imported_where_the_list_says() -> None:
    used = _scan()
    stale = [
        f"{module} {name} {where}: "
        + (
            f"imported in {', '.join(sorted(used[(module, name)]))}"
            if (module, name) in used
            else "the lab imports it nowhere"
        )
        for module, name, where in _listed()
        if where not in used.get((module, name), frozenset())
    ]
    assert not stale, (
        "these listed names are not imported where the list says:\n" + "\n".join(stale)
    )

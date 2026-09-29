# The lab's part of a split test file. The tests of this file that are the
# product's were removed here; they remain in the product's file at this path.
"""One door, ``python -m mcgyvr.serving.run`` — and the tree is scanned to prove it.

A design that says "one door" and never looks is true of an afternoon, not of the
instrument. The door is ``src/mcgyvr/serving/run.py``. It reaches no rig itself: it runs
the gate scripts in order, on a PATH whose ``ssh`` and ``docker`` are the shims under
``gate-scripts/bin``, and the one rule — a rig is reached under the door, and only to
the host the door was opened for — lives in ``gatelib.ssh`` and in the shims, which call
it. So the complete set of places a rig is touched from is small, and it is declared
HERE, each with a reason, so a new way to reach a rig has to be argued in a diff rather
than slipped in as a file.

THE ACCEPTED LIMIT, in one sentence: the proof every gate, step and driver
applies is an ancestor's command line plus RUN_HOST, both of which an
operator can forge with ``bash -c ... x/mcgyvr/serving/run.py``, so the seal
is against every code path in this repository and not against an operator
impersonating the door.

The tripwires, each a scan over the tree:

1. An ssh (or scp/rsync/sftp, a paramiko/fabric/asyncssh import, ``/usr/bin/
   ssh``, ``command -p ssh``) or a ``docker run`` appears in a code line only
   behind the door. A SPAWN, not the seam's name: a test that substitutes
   ``servelib.ssh``, and the stdlib result record a stub hands back, are the
   opposite of reaching a rig, and the scan reads those two spellings for
   what they are (``SEAM_MENTION``) instead of taking the bare word — while
   still scanning the whole of the rest of every such line.
2. Nothing under ``tools/`` or ``src/`` names its own daemon: no
   ``DOCKER_HOST``, no ``docker -H``/``--host``/``--context``, no ``-H ssh://``
   outside the shim, and no ``env -u``/``env -i`` that would strip the
   door's vocabulary.
3. No driver or campaign step measures ``localhost``: the container runs on
   the rig, and a client that polls this machine's loopback measures nothing.
4. The archived door's seam variables are gone from src, tools and tests.
5. The serving harness run bare — outside the door — exits 2 naming the door.
6. The workload (``PROMPT_DECILES``) is defined once, in
   ``tools/runs/workload.py``.
7. Every started artifact under ``records/evidence`` parses with
   ``tools.runs.rows.read``, and one that names a ``run_id`` also names its
   round.
8. Every host that wrote a row has a declared ``rig`` block in
   ``tools/runs/hosts.json``.
9. The retired entry points are gone.
10. A hand-set ``RUN_*`` environment admits nothing: a campaign step, the
    emitter's rig read, every driver, every gate script and the default
    step, given every variable the door would export and no door ancestor,
    exit 2 naming the door before an ``ssh`` or ``docker`` stub sees a line.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import sys
import types
from fnmatch import fnmatch
from pathlib import Path

import pytest

from mcgyvr.serving.run import EXPORTED
from tests._helpers import PRODUCT

REPO = Path(__file__).resolve().parent.parent
EVIDENCE = REPO / "records" / "evidence"
HOSTS = REPO / "tools" / "runs" / "hosts.json"
WORKLOAD = "tools/runs/workload.py"
DOOR = "python -m mcgyvr.serving.run"
SERVING_RUN = REPO / "tools" / "bench" / "serving" / "run.py"

#: Directories never scanned. ``records/`` and ``archive/`` are history and hold
#: the drivers as they ran; the rest is not this repository's code.
NOT_SCANNED = {"records", "archive", ".git", ".venv", "node_modules", "__pycache__"}

#: An ssh SPAWN, not a mention. The shell form wants an argument shaped like
#: one ssh takes — an option, a variable, ``user@host``, one of the rigs — so
#: prose such as "an ssh timeout" in a string is not a hit; scp, rsync and
#: sftp take a path first and are matched on any argument. The list form
#: (``["ssh", ...]``, ``["/usr/bin/ssh", ...]``) is what a subprocess argv
#: looks like: the shell pattern alone cannot see one, so without it a Python
#: file could open an ssh to a rig and never appear here.
SSH_SPAWN = re.compile(
    r"(?<![\w./-])(?:/usr/bin/)?ssh\s+(?:-[A-Za-z]|[\"']?\$|\{|[\w.-]+@|srv\d\b)"
    r"|(?<![\w./-])(?:scp|rsync|sftp)\s+(?=[\w$\"'{@./-])"
    r"|(?<![\w./-])/usr/bin/ssh\b"
    r"|(?<![\w./-])command\s+-p\s+ssh\b"
    r"|[\"'](?:/usr/bin/)?(?:ssh|scp|rsync|sftp)[\"']\s*,"
    r"|^\s*(?:import|from)\s+(?:paramiko|fabric|asyncssh)\b"
)
#: A container start: ``docker run ...`` in shell form, or the list form.
DOCKER_RUN = re.compile(
    r"(?<![\w./-])docker\s+run\s+(?=[\w$\"'{@.-])"
    r"|[\"']docker[\"']\s*,\s*[\"'](?:run|create|start)[\"']"
)
LOOPBACK = re.compile(r"\blocalhost\b|\b127\.0\.0\.1\b")

#: Two spellings in which the seam's NAME provably starts no process, erased from a line
#: before the spawn patterns read it. The list form above sees ``"ssh",`` and cannot
#: tell ``subprocess.run(["ssh", host])`` from a test taking that very call OUT of the
#: path. Both here are the second kind, and each is anchored on the construct that makes
#: it so:
#:
#: 1. ``monkeypatch.setattr(<module>, "ssh", fake)`` — pytest's fixture,
#:    REPLACING the seam. The opposite of reaching a rig, and the reason a
#:    probe test can substitute ``servelib.ssh`` and touch no machine.
#: 2. ``CompletedProcess(args=["ssh", host], returncode=..., ...)`` — the
#:    stdlib's RESULT record, which a stub hands back in place of a call that
#:    was never made. It is a plain container; running one is not among the
#:    things it can do. Two anchors, either of which settles it on its own:
#:    the constructor named on the line, or a ``returncode=`` beside the argv,
#:    which no spawning API in the stdlib accepts — ``subprocess.run`` and
#:    ``Popen`` both raise ``TypeError`` on it. So the second reads the
#:    constructor wrapped over two lines, which is how black formats it.
#:
#: Only the matched text is erased, never the file's text around it — deleting
#: more would hide a real spawn written the same way — and the whole of the rest
#: of the line is still scanned. An argv, a command string or a
#: second seam anywhere else on the line survives the erasure and is still a
#: hit, INCLUDING inside the substitute itself:
#: ``monkeypatch.setattr(servelib, "ssh", lambda h: run(["ssh", h]))`` is
#: caught on its second ``"ssh",``. Neither spelling can be reached by
#: accident either: a bare ``setattr`` is not exempt, only ``monkeypatch.``'s,
#: and both require the seam to be the FIRST element of the argv, so
#: ``run(args=["env", "ssh", h])`` is untouched. The substitution is
#: deliberately single-line: one wrapped over two leaves ``servelib, "ssh",
#: rig`` alone on one of them and is a hit, which is the safe way to fail.
SEAM_MENTION = re.compile(
    r"\bmonkeypatch\.setattr\(\s*[A-Za-z_][\w.]*\s*,\s*"
    r"[\"'](?:/usr/bin/)?(?:ssh|scp|rsync|sftp)[\"']\s*,"
    r"|(?<![\w.])(?:subprocess\.)?CompletedProcess\(\s*args\s*=\s*\[\s*"
    r"[\"'](?:/usr/bin/)?(?:ssh|scp|rsync|sftp)[\"']\s*,"
    r"|\bargs\s*=\s*\[\s*[\"'](?:/usr/bin/)?(?:ssh|scp|rsync|sftp)[\"']\s*,"
    r"(?=[^()]*\breturncode\s*=)"
)


def _scanned(line: str) -> str:
    """The line as every pattern here reads it: a :data:`SEAM_MENTION` erased,
    and nothing else on the line touched."""
    return SEAM_MENTION.sub(" <seam mention> ", line)


#: The lab's test files a spawn pattern may hit. Path glob -> why that hit
#: reaches no rig. ``fnmatch`` semantics: ``*`` crosses ``/``.
ALLOWED: dict[str, str] = {
    "tests/onedoor.py": (
        "the door tests' stubs: `ssh_stub` writes the `ssh` that stands behind "
        "the shim, a script that logs and answers and reaches nothing; the argv "
        "the list-form pattern sees is that file's name"
    ),
    "tests/test_one_door.py": (
        "this file names the patterns it scans for, and writes the `ssh` and "
        "`docker` stubs its refusal tests run against, which log every argv and "
        "fail"
    ),
    "tests/test_a_failed_lock_fleets_start_keeps_its_full_log_and_gets_one_retry.py": (
        "runs lock-fleets' step bodies under a fake door with an ssh and a docker "
        "stub standing under RUN_BIN, and finds the move shell's `docker run -d` "
        "in the stub's call log; reaches no rig"
    ),
    "tests/test_lock_fleets_files_an_exit_cause_and_one_diagnostic_start.py": (
        "runs lock-fleets' unit step under a fake door with an ssh and a docker "
        "stub standing under RUN_BIN, which answer the container's State and the "
        "rig's kernel log from files the test writes; reaches no rig"
    ),
    "tests/test_default_step.py": (
        "drives the shipped default step under a stand-in door, with answering "
        "ssh and docker stubs at the shim path it names as RUN_BIN and decoys "
        "under the same names on PATH that log and fail; reaches no rig"
    ),
    "tests/test_cross_rig_claim.py": (
        "monkeypatches contract.ssh with a lambda that answers the health probe; "
        "the call is wrapped over lines, so the seam's name stands on a line of "
        "its own; reaches no rig"
    ),
    "tests/test_serving.py": (
        "monkeypatches contract.ssh with a lambda that returns canned text; "
        "reaches no rig"
    ),
    "tests/test_sink_conformance.py": (
        "replaces the vLLM backend's contract.ssh with a local function that "
        "answers canned readings, under pytest.MonkeyPatch.context() bound as "
        "`patch`, a spelling the seam erasure does not read; reaches no rig"
    ),
    "tests/test_serving_memory_declaration.py": (
        "reads the vLLM backend's `_start` as text and asserts its `docker run "
        "-d` launch line is built after the declaration is checked; runs nothing"
    ),
}

DECILES = re.compile(r"^\s*PROMPT_DECILES\s*=")


def _code_lines(text: str) -> list[str]:
    """Line-oriented, deliberately crude: drop comment and docstring lines."""
    out: list[str] = []
    in_doc = False
    for raw in text.splitlines():
        line = raw.strip()
        fences = line.count('"""') + line.count("'''")
        if in_doc:
            if fences:
                in_doc = False
            continue
        if line.startswith("#"):
            continue
        if fences == 1:
            in_doc = True
            continue
        out.append(line)
    return out


def _is_source(path: Path) -> bool:
    """``*.py``, ``*.sh``, and a suffix-less executable (the shims)."""
    if path.suffix in (".py", ".sh"):
        return True
    return not path.suffix and path.is_file() and bool(path.stat().st_mode & 0o111)


def _sources(roots: tuple[str, ...], root_files: bool) -> list[Path]:
    """Every source file under ``roots`` (recursive), plus the repo root."""
    found: list[Path] = []
    for top in roots:
        for path in (REPO / top).rglob("*"):
            if not _is_source(path):
                continue
            if NOT_SCANNED & set(path.relative_to(REPO).parts):
                continue
            found.append(path)
    if root_files:
        found += [p for p in REPO.iterdir() if p.suffix in (".py", ".sh")]
    return sorted(found)


def _rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def _allowed(rel: str) -> bool:
    return any(fnmatch(rel, pattern) for pattern in ALLOWED)


def _matching(pattern: re.Pattern[str], text: str) -> list[str]:
    """Every code line of ``text`` the pattern hits, seam mentions erased.

    The whole decision, in one place, so the test that pins it below is asking
    the same question of the same code the tree-wide scans ask.
    """
    return [line[:100] for line in _code_lines(text) if pattern.search(_scanned(line))]


def _hits(
    pattern: re.Pattern[str], roots: tuple[str, ...], *, root_files: bool = False
) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for path in _sources(roots, root_files=root_files):
        lines = _matching(pattern, path.read_text(encoding="utf-8", errors="replace"))
        if lines:
            hits[_rel(path)] = lines
    return hits


def _rows() -> types.ModuleType:
    """``tools/runs/rows.py`` — the parser, at the home the door reads it from."""
    return importlib.import_module("tools.runs.rows")


def _started() -> list[Path]:
    """Every artifact that carries a ``### START`` line."""
    return [
        path
        for path in sorted(EVIDENCE.rglob("*.tsv"))
        if any(
            line.startswith("### START")
            for line in path.read_text(encoding="utf-8").splitlines()
        )
    ]


# --------------------------------------------------------------------------
# 1. an ssh or a docker run appears only behind the door
# --------------------------------------------------------------------------


def test_an_ssh_or_a_docker_run_in_a_lab_test_is_argued_in_allowed() -> None:
    """The lab's tests reach no rig: every spawn-shaped line is argued here.

    A hit in a file of ``tests/`` is a stub, a stand-in or a line of text
    about one, and ``ALLOWED`` says which for each file. A new file with a
    hit fails until it is argued into ``ALLOWED`` with its reason, or the
    spawn is removed.
    """
    hits = _hits(SSH_SPAWN, ("tests",))
    for rel, lines in _hits(DOCKER_RUN, ("tests",)).items():
        hits.setdefault(rel, []).extend(lines)
    assert hits, "the scan found no invocation at all — the pattern is broken"
    strays = {rel: lines for rel, lines in hits.items() if not _allowed(rel)}
    assert not strays, (
        f"{len(strays)} lab test file(s) hold a spawn outside {DOOR} that "
        "ALLOWED does not argue — each is (path, invocations) and is argued "
        f"into ALLOWED with a reason or removed: {strays}"
    )


def test_every_allowed_entry_names_a_file_that_exists() -> None:
    """A stale allowance is a hole waiting for a file of that name."""
    present = [_rel(p) for p in _sources(("tests",), root_files=False)]
    stale = [
        pattern
        for pattern in ALLOWED
        if not any(fnmatch(rel, pattern) for rel in present)
    ]
    assert not stale, f"ALLOWED names files that do not exist: {stale}"


def test_the_serving_harness_spawns_no_ssh_of_its_own() -> None:
    """``tools/bench/serving/*`` reaches a rig only through ``contract.ssh``,
    which is ``gatelib.ssh``; the `docker run` lines it carries are command
    text shipped over that ssh. No ssh spawn of its own, in any form."""
    hits = _hits(SSH_SPAWN, ("tools/bench/serving",))
    assert not hits, f"the serving harness spawns an ssh outside gatelib: {hits}"


# --------------------------------------------------------------------------
# 2. nothing names its own daemon; 3. nothing measures loopback; 4. no seams
# --------------------------------------------------------------------------


#: Campaign files whose loopback is the RIG's: shell text sent over the door's
#: ssh and run on the rig, never on this machine. Path -> why.
LOOPBACK_ON_THE_RIG: dict[str, str] = {
    "tools/runs/campaigns/srv1-cpu-saturation/cpusat.py": (
        "the probe's aggregate pass: this file is shipped to the rig on stdin "
        "(`python3 - rig-agg`, as the lock's harness is) over the door's ssh "
        "and posts to the rig's own 127.0.0.1; the step itself polls nothing "
        "here (owner, 2026-09-16, srv1-cpu-saturation)"
    ),
    "tools/runs/campaigns/lock-fleets/_move.sh": (
        "the move stopwatch: ONE ssh argv, run on the rig, polls each target unit "
        "at the rig's own 127.0.0.1 and stamps it with the rig's clock (owner "
        "ruling 2026-09-15, lock-fleets); the step itself polls nothing here"
    ),
}


def test_no_driver_or_campaign_step_measures_loopback() -> None:
    hits = _hits(LOOPBACK, ("tools/runs/drivers", "tools/runs/campaigns"))
    for rel in LOOPBACK_ON_THE_RIG:
        assert (REPO / rel).is_file(), (
            f"{rel} is allowed the rig's loopback and is gone"
        )
        hits.pop(rel, None)
    assert not hits, (
        "the container runs on the rig (the door's `docker` lands there), so a "
        f"client polling this machine's loopback measures nothing: {hits}"
    )


# --------------------------------------------------------------------------
# 5. the serving harness run bare exits 2 naming the door
# --------------------------------------------------------------------------


def test_the_serving_harness_run_bare_exits_2_naming_the_door(tmp_path: Path) -> None:
    """``tests/test_serving_gatelib.py`` pins ``gatelib.ssh``'s refusal and
    ``tests/test_serving_door_cli.py`` the shims' and the gates'; this is the
    harness as an operator would run it by hand, from the outside."""
    config = tmp_path / "min.json"
    config.write_text(
        json.dumps({"hosts": ["h"], "backends": [], "models": []}), encoding="utf-8"
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith(("RUN_", "DOCKER_"))}
    done = subprocess.run(
        [
            sys.executable,
            str(SERVING_RUN),
            "--config",
            str(config),
            "--out",
            str(tmp_path / "survey.jsonl"),
        ],
        cwd=REPO,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert done.returncode == 2, (done.returncode, done.stdout[-400:], done.stderr)
    assert DOOR in done.stderr, done.stderr[-600:]
    assert "not started by the door" in done.stderr, done.stderr[-600:]


# --------------------------------------------------------------------------
# 10. a hand-set RUN_* environment admits nothing
# --------------------------------------------------------------------------

GATE_SCRIPTS = PRODUCT / "src" / "mcgyvr" / "serving" / "gate-scripts"
DEFAULT_STEP = GATE_SCRIPTS / "default-step.sh"
COMMON_SH = REPO / "tools" / "runs" / "_common.sh"
KERNEL_ARMS_STEP = (
    REPO / "tools" / "runs" / "campaigns" / "srv1-kernel-arms" / "4-kernel-arms.sh"
)
DRIVERS = REPO / "tools" / "runs" / "drivers"
#: Each driver's image variable and an argv past ``sys.argv``; the image IS a
#: digest, so the door's proof is the only refusal left between it and docker.
DRIVER_CALLS: dict[str, tuple[str, list[str]]] = {
    "lcp_sweep.py": ("LCP_IMG", ["/models/x.gguf", "/models", "tag", "1:4096:0:1"]),
    "mgpu_sweep.py": ("VLLM_IMG", ["vllm", "tag:org/model:tp2:on:2048:1"]),
    "vllm_sweep.py": ("VLLM_IMG", ["tag", "org/model", "0.9:2048:8:auto:1"]),
    "vllm_cores.py": (
        "VLLM_IMG",
        ["pair", "0.45", "2048", "128", "auto", "1", "a=org/model"],
    ),
}
ZERO_DIGEST = "sha256:" + "0" * 64


def _stubs(where: Path) -> Path:
    """An ``ssh`` and a ``docker`` that log every argv and fail. Nothing in
    this section may reach either; the absence of a log is the evidence."""
    where.mkdir(parents=True, exist_ok=True)
    for name in ("ssh", "docker"):
        path = where / name
        path.write_text(
            "#!/usr/bin/env bash\n"
            f"printf '%s\\n' \"$*\" >> '{where / (name + '.log')}'\n"
            "exit 1\n",
            encoding="utf-8",
        )
        path.chmod(0o755)
    return where


def _reached(stubs: Path) -> list[str]:
    return sorted(
        f"{p.name}: {p.read_text(encoding='utf-8')}" for p in stubs.glob("*.log")
    )


def _hand_set(stubs: Path, tmp_path: Path, **only: str) -> dict[str, str]:
    """Every ``RUN_*`` the door would export, typed in by hand — or just
    ``only`` — with the stubs first on PATH and the test interpreter next, so
    a bash proof finds a python3 that CAN import gatelib and still says no."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("RUN_", "DOCKER_"))}
    parts = [str(stubs), str(Path(sys.executable).parent)]
    parts += (env.get("PATH") or os.defpath).split(os.pathsep)
    env["PATH"] = os.pathsep.join(parts)
    if only:
        env.update(only)
        return env
    out_dir = tmp_path / "envelope"
    out_dir.mkdir(exist_ok=True)
    env.update(dict.fromkeys(EXPORTED, "x"))
    env.update(
        RUN_ROOT=str(REPO),
        RUN_BIN=str(PRODUCT / "src" / "mcgyvr" / "serving" / "gate-scripts" / "bin"),
        RUN_REPO=str(REPO),
        RUN_HOST="srv1",
        RUN_ID="2026-09-05-srv1-kernel-arms-kernel-arms",
        RUN_OUT_DIR=str(out_dir),
        RUN_ROUND="r3-05-09-2026",
        RUN_PRODUCT_SHA256="0" * 64,
        RUN_STEP="kernel-arms",
        RUN_CAMPAIGN="srv1-kernel-arms",
        RUN_MODEL="/models/x.gguf",
        RUN_STEP_FILE=str(DEFAULT_STEP),
        RUN_PARALLEL="1",
        RUN_CTX_PER_SLOT="4096",
        RUN_UBATCH="512",
        RUN_DATE="2026-09-05",
        RUN_SUFFIX="",
        RUN_EXPORT_FD="1",
        RUN_SCAN_JSON=str(out_dir / "scan.json"),
        RUN_GEOMETRY_JSON=str(out_dir / "geometry.json"),
        RUN_PLACEMENT_JSON=str(out_dir / "placement.json"),
    )
    return env


def _outside(argv: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run ``argv`` with no door anywhere above it."""
    return subprocess.run(
        argv,
        cwd=REPO,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _refused_naming_the_door(
    done: subprocess.CompletedProcess[str], stubs: Path, what: str
) -> None:
    assert done.returncode == 2, (
        what,
        done.returncode,
        done.stdout[-400:],
        done.stderr,
    )
    assert DOOR in done.stderr, (what, done.stderr[-800:])
    assert _reached(stubs) == [], f"{what} reached a stub outside the door"


def test_a_campaign_step_with_every_run_variable_typed_in_is_refused_outside_the_door(
    tmp_path: Path,
) -> None:
    """``RUN_ID=x RUN_HOST=srv1 ... bash 4-kernel-arms.sh --models ...`` by
    hand, with every variable the door exports: it once passed door_required
    on the environment alone and went on to ``ssh srv1``."""
    stubs = _stubs(tmp_path / "stubs")
    done = _outside(
        ["bash", str(KERNEL_ARMS_STEP), "--models", "/models/x.gguf"],
        _hand_set(stubs, tmp_path),
    )
    _refused_naming_the_door(done, stubs, "4-kernel-arms.sh")


@pytest.mark.parametrize("full", [False, True], ids=["RUN_HOST-only", "every-RUN_*"])
def test_rig_snapshot_by_hand_is_refused_before_ssh(tmp_path: Path, full: bool) -> None:
    stubs = _stubs(tmp_path / "stubs")
    env = (
        _hand_set(stubs, tmp_path)
        if full
        else _hand_set(stubs, tmp_path, RUN_HOST="srv1")
    )
    done = _outside(["bash", "-c", f". '{COMMON_SH}'; rig_snapshot"], env)
    _refused_naming_the_door(done, stubs, "rig_snapshot")


@pytest.mark.parametrize("name", sorted(DRIVER_CALLS))
def test_a_driver_with_a_run_id_and_a_digest_is_refused_outside_the_door(
    tmp_path: Path, name: str
) -> None:
    stubs = _stubs(tmp_path / "stubs")
    variable, argv = DRIVER_CALLS[name]
    env = _hand_set(
        stubs, tmp_path, RUN_ID="x", RUN_HOST="srv1", **{variable: ZERO_DIGEST}
    )
    done = _outside([sys.executable, str(DRIVERS / name), *argv], env)
    _refused_naming_the_door(done, stubs, name)


# --------------------------------------------------------------------------
# 6. one workload
# --------------------------------------------------------------------------


def test_the_workload_is_defined_once_in_workload_py() -> None:
    definitions = sorted(
        _rel(path)
        for path in _sources(("src", "tools", "tests", "okf", "data"), root_files=True)
        if any(DECILES.search(line) for line in _code_lines(path.read_text("utf-8")))
    )
    assert definitions == [WORKLOAD], (
        f"PROMPT_DECILES is defined in {definitions}; the one definition is "
        f"{WORKLOAD}, which every driver imports. A second copy is a second "
        "workload that will drift — the 2f2bb793 digest is over generated prompts "
        "precisely so no copy can be equal by accident."
    )


# --------------------------------------------------------------------------
# 7. every started artifact parses; a run_id brings its round
# --------------------------------------------------------------------------


def test_every_started_artifact_parses_and_a_run_id_names_its_round() -> None:
    rows = _rows()
    started = _started()
    assert started, f"no artifact under {EVIDENCE} carries a ### START line"
    problems: list[str] = []
    for path in started:
        rel = _rel(path)
        try:
            sweep = rows.read(path)
        except ValueError as error:
            problems.append(f"{rel}: does not parse — {error}")
            continue
        starts = [
            line
            for _, line in sweep.markers
            if line.removeprefix("###").split()[:1] == ["START"]
        ]
        if not any("run_id=" in line for line in starts):
            continue  # pre-door artifact: no run_id, no round is owed
        try:
            start, round_ = sweep.stamp("START"), sweep.stamp("ROUND")
        except ValueError as error:
            problems.append(f"{rel}: a stamp does not parse — {error}")
            continue
        if not start.get("run_id"):
            problems.append(f"{rel}: START names run_id= but it is empty")
        if not (round_.get("id") and round_.get("product_sha256")):
            problems.append(
                f"{rel}: START carries run_id={start.get('run_id')!r} but no "
                "`### ROUND id= product_sha256=` — a run the door started stamps "
                "the product round it measured (gate 1)"
            )
    assert not problems, "\n".join(problems)


# --------------------------------------------------------------------------
# 8. every host that wrote a row is declared
# --------------------------------------------------------------------------


def test_every_host_that_wrote_a_row_has_a_declared_rig() -> None:
    rows = _rows()
    hosts = sorted({row.host for path in _started() for row in rows.read(path).rows})
    assert hosts, "no artifact carries a row, so no host is on record"
    declared = json.loads(HOSTS.read_text(encoding="utf-8"))
    gaps: list[str] = []
    for host in hosts:
        rig = (declared.get(host) or {}).get("rig")
        if not isinstance(rig, dict):
            gaps.append(
                f"{host}: no `rig` block under {HOSTS.relative_to(REPO)}[{host!r}]"
            )
            continue
        missing = [f for f in rows.RIG_FIELDS if not str(rig.get(f, "")).strip()]
        if missing:
            gaps.append(f"{host}: rig block lacks {missing}")
        if not str(declared[host].get("read_on", "")).strip():
            gaps.append(f"{host}: no read_on beside the rig block — read when?")
    assert not gaps, (
        "gate 2 compares the live rig with its declaration, so every host that "
        f"ever wrote a row must be declared: {gaps}"
    )


# --------------------------------------------------------------------------
# 9. the retired entry points are gone
# --------------------------------------------------------------------------


#: The owner ruled that the 21 files below keep the executable
#: bit they were recorded with: a record is evidence, not something changed to
#: suit a test. This is that one exact folder, never a pattern another folder
#: could also match, and the set is pinned here, read from git with
#: ``git ls-files -s`` (mode ``100755``) over that folder. The test below
#: reads the files on disk: when the set of files there that carry an exec bit
#: differs from this list, it fails and names the files.
RECORDED_EXECUTABLE_DIR = "records/measurements/quick-check-2026-09-15"
RECORDED_EXECUTABLE = frozenset(
    f"{RECORDED_EXECUTABLE_DIR}/{rest}"
    for rest in (
        "drive.sh",
        "refused-r28/srv2/apto-as_Qwen2.5-Coder-7B-Instruct-Q5_K_M-GGUF.bench-py.stdout",
        "refused-r28/srv2/apto-as_Qwen2.5-Coder-7B-Instruct-Q5_K_M-GGUF.bench-ts.stdout",
        "refused-r28/srv2/apto-as_Qwen2.5-Coder-7B-Instruct-Q5_K_M-GGUF.launch.txt",
        "srv1/Qwen_Qwen2.5-Coder-0.5B-Instruct-GGUF.bench-py.stdout",
        "srv1/Qwen_Qwen2.5-Coder-0.5B-Instruct-GGUF.bench-ts.stdout",
        "srv1/Qwen_Qwen2.5-Coder-0.5B-Instruct-GGUF.launch.txt",
        "srv1/Qwen_Qwen2.5-Coder-0.5B-Instruct-GGUF/bench-py/run.json",
        "srv1/Qwen_Qwen2.5-Coder-0.5B-Instruct-GGUF/bench-ts/run.json",
        "srv1/Qwen_Qwen2.5-Coder-1.5B-Instruct-GGUF.launch.txt",
        "srv2/apto-as_Qwen2.5-Coder-7B-Instruct-Q5_K_M-GGUF.bench-py.stdout",
        "srv2/apto-as_Qwen2.5-Coder-7B-Instruct-Q5_K_M-GGUF.bench-ts.stdout",
        "srv2/apto-as_Qwen2.5-Coder-7B-Instruct-Q5_K_M-GGUF.launch.txt",
        "srv2/apto-as_Qwen2.5-Coder-7B-Instruct-Q5_K_M-GGUF/bench-py/run.json",
        "srv2/apto-as_Qwen2.5-Coder-7B-Instruct-Q5_K_M-GGUF/bench-ts/run.json",
        "srv2/yuxinlu1_gemma-4-12B-coder-fable5-composer2.5-v1-GGUF.bench-py.stdout",
        "srv2/yuxinlu1_gemma-4-12B-coder-fable5-composer2.5-v1-GGUF.bench-ts.stdout",
        "srv2/yuxinlu1_gemma-4-12B-coder-fable5-composer2.5-v1-GGUF.launch.txt",
        "srv2/yuxinlu1_gemma-4-12B-coder-fable5-composer2.5-v1-GGUF/bench-py/run.json",
        "srv2/yuxinlu1_gemma-4-12B-coder-fable5-composer2.5-v1-GGUF/bench-ts/run.json",
        "summarise.py",
    )
)
assert len(RECORDED_EXECUTABLE) == 21


def test_nothing_under_records_is_executable() -> None:
    """Nothing under ``records/`` is executable, except the 21 files pinned in
    :data:`RECORDED_EXECUTABLE`, under :data:`RECORDED_EXECUTABLE_DIR`. The
    owner ruled that those files keep the mode they were recorded with — they
    are history, not an entry point, and are not changed to suit this test.
    Any other file under ``records/`` that carries an exec bit fails this
    test, and so does one of the 21 that no longer carries it."""
    executable = sorted(
        _rel(path)
        for path in (REPO / "records").rglob("*")
        if path.is_file() and path.stat().st_mode & 0o111
    )
    unnamed = [path for path in executable if path not in RECORDED_EXECUTABLE]
    assert not unnamed, (
        f"{len(unnamed)} file(s) under records/ carry the exec bit and are not "
        f"among the {len(RECORDED_EXECUTABLE)} named in RECORDED_EXECUTABLE — a "
        f"record is evidence, not an entry point: {unnamed}"
    )
    recorded = sorted(path for path in executable if path in RECORDED_EXECUTABLE)
    assert recorded == sorted(RECORDED_EXECUTABLE), (
        f"the executable set under {RECORDED_EXECUTABLE_DIR} no longer matches "
        f"what the owner's ruling pinned — found {recorded}, expected "
        f"{sorted(RECORDED_EXECUTABLE)}"
    )


@pytest.mark.parametrize(
    "pattern",
    [
        "run-with-bench-prompts",
        "tools/bench/serving/sweep.py",
        "lcp-vllm-3-arm-run.md",
        "tools/runs/srv1-*.sh",
        "tools/runs/run.sh",
        "tools/runs/campaigns/srv1-kernel-arms/PLAN.md",
        # The readers moved into the product with the door (round r3).
        "tools/bench/serving/ggufscan.py",
        "tools/bench/serving/vramfit.py",
    ],
)
def test_the_retired_entry_point_is_gone(pattern: str) -> None:
    present = sorted(_rel(p) for p in REPO.glob(pattern))
    assert not present, f"{present} still exist(s); {DOOR} is the only door"

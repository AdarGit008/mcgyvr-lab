# The lab's copy. The tests of this file that are the product's were removed
# here; they remain in the product's copy of this file.
"""The door refuses before it acts, and what it starts cannot leave it.

``python -m mcgyvr.serving.run`` is the one access point to the rigs. Pinned
here, from the outside, the way an operator meets it:

* an ambient ``RUN_*`` or ``DOCKER_*`` variable is refused by name before any
  gate — the door mints its own vocabulary;
* ``--help`` shows no ``--skip``, ``--force`` or ``--no-`` anything, and
  ``--step`` is optional (the shipped default step);
* a step argument that would write outside the envelope is refused before
  gate 1, and one naming a path inside it is admitted;
* the ``ssh`` and ``docker`` on the PATH the door exports are shims: outside
  the door they exit 2 naming it, under it they become the real binary
  pointed at the door's host and nothing else;
* every gate script run by hand exits 2;
* an interrupt during the step still runs gates 7 and 8, then exits 130.

No test here reaches a rig: every door invocation has a stub ``ssh`` and a
stub ``docker`` on PATH behind the shims, and the interrupt path is driven
through fake gates that export what the real ones declare. None files under
the checkout either: every door runs with ``MCGYVR_RUN_ROOT`` naming a
throw-away checkout (:func:`root`), so a round gate 1 opens is written there.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from mcgyvr.serving import run
from tests import onedoor
from tests._helpers import PRODUCT

REPO = Path(__file__).resolve().parent.parent
GATE_SCRIPTS = PRODUCT / "src" / "mcgyvr" / "serving" / "gate-scripts"
BIN = GATE_SCRIPTS / "bin"
DOCKER = "docker"
RUN_DATE = "2026-09-02"
# SSH, clean_env and executable are copies of the three the product's
# tests/test_serving_gatelib.py defines; that module stays in the product.
SSH = "ssh"


def clean_env(*path_first: Path) -> dict[str, str]:
    """No RUN_* or DOCKER_* inherited; the venv's interpreter first on PATH."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("RUN_", "DOCKER_"))}
    parts = [str(p) for p in path_first] + [str(Path(sys.executable).parent)]
    parts += (env.get("PATH") or os.defpath).split(os.pathsep)
    env["PATH"] = os.pathsep.join(parts)
    return env


def executable(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


#: The checkout's record of rounds. A run whose tree has moved off the open
#: round appends one to its root's copy, and this one is tracked and read by
#: every other xdist worker while these tests run — so no door here runs from
#: the checkout (:func:`root`), and this is only ever read.
ROUNDS = REPO / "tools" / "bench" / "rounds.json"


def stubs(where: Path) -> Path:
    """An ``ssh`` that refuses and a ``docker`` that logs, both behind the shims."""
    executable(
        where / SSH,
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$*\" >> '{where / 'ssh.log'}'\n"
        "echo 'no rig is reachable from a test' >&2\n"
        "exit 1\n",
    )
    executable(
        where / DOCKER,
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$*\" >> '{where / 'docker.log'}'\n"
        "exit 0\n",
    )
    return where


def door(
    argv: list[str], env: dict[str, str], cwd: Path = REPO
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mcgyvr.serving.run", *argv],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """The run root every door here files under: a throw-away checkout pinned
    as built, so gate 1 admits its tree and writes nothing unless a test moves
    it — and whatever it does write is under ``tmp_path``, never the checkout."""
    return onedoor.fixture_repo(tmp_path / "root")


@pytest.fixture
def env(tmp_path: Path, root: Path) -> dict[str, str]:
    environment = clean_env(stubs(tmp_path / "stubs"))
    environment[run.ROOT_ENV] = str(root)
    return environment


@pytest.fixture
def step(tmp_path: Path) -> Path:
    return executable(
        tmp_path / "1-probe.sh", "#!/usr/bin/env bash\n# RUN_ARTIFACTS: probe.tsv\n"
    )


def base_argv(step: Path, campaign: str = "alpha-cli-test") -> list[str]:
    return [
        "--host",
        "srv1",
        "--campaign",
        campaign,
        "--model",
        "/models/x.gguf",
        "--step",
        str(step),
        "--date",
        RUN_DATE,
        # The window the run serves. Required rather than defaulted, so the
        # door holds no context number of its own
        # (tests/red_port/test_dod_one_context_number.py).
        "--ctx-per-slot",
        "4096",
    ]


# --------------------------------------------------------------------------
# before any gate: the environment, the arguments
# --------------------------------------------------------------------------


def test_the_default_step_is_taken_when_none_is_named(
    env: dict[str, str], step: Path
) -> None:
    argv = [a for a in base_argv(step) if a not in ("--step", str(step))]
    result = door(argv, env)
    assert result.returncode == 2, (result.stdout, result.stderr)
    if run.DEFAULT_STEP.is_file():
        assert "the default step is missing" not in result.stderr, result.stderr
    else:
        assert "the default step is missing" in result.stderr, result.stderr
        assert str(run.DEFAULT_STEP.relative_to(run.ROOT)) in result.stderr


ESCAPES = (
    ["--out", "/tmp/elsewhere.tsv"],
    ["--out=/tmp/elsewhere.tsv"],
    ["--out-dir", "/tmp/elsewhere"],
    ["--out-dir=/tmp/elsewhere"],
    ["--force"],
    ["--out", "records/evidence/2026-09-01-other/x.tsv"],
    ["--out", "../outside.tsv"],
)


@pytest.mark.parametrize(
    "args", ESCAPES, ids=[a[0].split("=")[0] + str(i) for i, a in enumerate(ESCAPES)]
)
def test_a_step_argument_that_leaves_the_envelope_is_refused_before_any_gate(
    env: dict[str, str], step: Path, tmp_path: Path, root: Path, args: list[str]
) -> None:
    result = door([*base_argv(step), "--", *args], env)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "step argument" in result.stderr, result.stderr
    assert args[0].split("=")[0] in result.stderr, result.stderr
    assert f"{RUN_DATE}-alpha-cli-test" in result.stderr, result.stderr
    for where in (REPO, root):
        assert not (
            where / "records" / "evidence" / f"{RUN_DATE}-alpha-cli-test"
        ).exists()
    assert not (tmp_path / "stubs" / "ssh.log").exists(), "a gate reached ssh"


def test_a_step_argument_inside_the_envelope_is_admitted(
    env: dict[str, str], step: Path
) -> None:
    inside = f"records/evidence/{RUN_DATE}-alpha-cli-test/probe.tsv"
    result = door([*base_argv(step), "--", "--out", inside], env)
    # It goes on to gate 1 (or 2, where the stub refuses); it is not the
    # argument check that stopped it.
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "step argument" not in result.stderr, result.stderr


def test_a_round_gate_1_opens_for_these_tests_lands_in_their_own_root(
    env: dict[str, str], step: Path, tmp_path: Path
) -> None:
    """Gate 1 appends a round when the tree it measures has moved off the open
    one, which is the door's job. From the checkout that append lands in the
    tracked ``tools/bench/rounds.json`` while every other xdist worker reads
    it, so the door these tests start measures a root under ``tmp_path`` —
    moved off its round here, so gate 1 has a round to open."""
    named = env.get(run.ROOT_ENV)
    root = Path(named) if named else run.ROOT
    assert tmp_path in root.parents, (
        f"the door these tests start runs from {root}, so gate 1 opens its "
        f"rounds in {ROUNDS} while other xdist workers are reading it"
    )
    onedoor.unpin(root)
    checkout = ROUNDS.read_bytes()

    result = door(base_argv(step), env)

    assert result.returncode == 2, (result.stdout, result.stderr)
    assert onedoor.pinned(root)[0] != onedoor.ROUND_ID, (
        "gate 1 opened no round in the test's own root",
        result.stderr,
    )
    assert ROUNDS.read_bytes() == checkout, f"a door run from a test wrote {ROUNDS}"


def test_check_step_args_reads_the_archived_rule() -> None:
    envelope = run.ROOT / "records" / "evidence" / "2026-09-02-alpha"
    assert run._check_step_args([], envelope) is None
    assert (
        run._check_step_args(["--model", "/models/x.gguf", "-n", "8"], envelope) is None
    )
    assert run._check_step_args(["--out", str(envelope / "a.tsv")], envelope) is None
    for tokens in (["--out"], ["--out="], ["--out-dir", "/tmp"], ["--force"]):
        rule = run._check_step_args(tokens, envelope)
        assert rule is not None and "step argument" in rule, tokens


# --------------------------------------------------------------------------
# the manifest: shims are part of the door
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# the shims themselves
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# the gates by hand
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# the interrupt path: gates 7 and 8 run, then 130
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model",
    [
        "/models/x.gguf; touch /tmp/pwned",
        "/models/x.gguf$(id)",
        "/models/x.gguf`id`",
        "/models/a b.gguf",
        "/models/x.gguf|id",
        "models/x.gguf",
        "/models/../etc/passwd",
        "/models//x.gguf",
    ],
)
def test_a_model_path_with_shell_characters_is_refused_before_any_gate(
    env: dict[str, str], step: Path, tmp_path: Path, model: str
) -> None:
    """--model is handed to a remote shell by data-20 and to container argv by
    the step; the door refuses anything but an absolute path of ordinary
    characters, before gate 1, so nothing is ever escaped in three places."""
    argv = [a for a in base_argv(step)]
    argv[argv.index("--model") + 1] = model
    result = door(argv, env)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "--model" in result.stderr and "refused" in result.stderr, result.stderr
    assert not (tmp_path / "stubs" / "ssh.log").exists(), "a gate reached ssh"


def test_data_20_quotes_the_remote_path_even_so() -> None:
    """The second lock on the same door: the remote line data-20 builds leaves
    only `$HOME` bare, so a path that somehow carried a shell character is a
    file name on the rig and never a command."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "data_20_geometry",
        PRODUCT / "src" / "mcgyvr" / "serving" / "gate-scripts" / "data-20-geometry.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    line = module.scan_command("QUJD", "/models/x.gguf; touch /tmp/pwned")
    assert line.endswith("""python3 - "$HOME"/models'/x.gguf; touch /tmp/pwned'"""), (
        line
    )
    assert module.scan_command("QUJD", "/models/moe/x.gguf").endswith(
        'python3 - "$HOME"/models/moe/x.gguf'
    )
    assert module.scan_command("QUJD", "/srv/blob.gguf").endswith(
        "python3 - /srv/blob.gguf"
    )

# The lab's part of a split test file. The tests of this file that are the
# product's were removed here; they remain in the product's file at this path.
"""A live unit is judged only by a solo probe run with its lock's own method.

Owner ruling F2: every dispatch row keeps its decode, prefill and in-flight
figures as data, and only a probe judges. The lock is measured at a short
prompt and 256 tokens out, so a dispatch is not the lock's quantity.

* **The probe repeats the lock's measurement.** A vLLM unit gets
  ``records/measurements/fleet-setup-2026-09-13/srv2/measure_vllm.py``: one
  64-token warm-up, five 256-token decodes (``completion_tokens`` over wall
  seconds) and three 16-token prefills of the long prompt (``prompt_tokens``
  over wall seconds). A llama.cpp unit gets
  ``records/measurements/fleet-setup-2026-09-13/srv1/harness_llama.py``:
  ``/completion`` with ``timings``. Both take the median, as the lock did
  (``mcgyvr-lab/fleet-setup/REPORT-srv1.md``, ``REPORT-srv2.md``).
* **It probes only an idle unit.** It reads the unit's own count first and
  again after; a unit busy before is not probed, and one busy after is filed
  as contended and not judged.
* **It stamps every observation** with the fleet, rig, rig id, combination id
  and unit id of the live lock, and files them under ``<journal.dir>/fleet/``.
* **A vLLM figure timed off the rig is recorded, not judged.** Given a reader
  (:func:`mcgyvr.fleet.read.spawn_read`) the vLLM measurement runs on the rig
  behind the door, where ``measure_vllm.py`` times at 127.0.0.1, and is judged
  there. A probe with no reader, or a rig whose read filed nothing, times vLLM
  by wall clock from off the rig, at the unit's address, and records it. A
  llama.cpp figure is the server's own ``timings``, and is judged either way.
* **The tolerance is one class per unit.** vLLM is ``vllm``; llama.cpp with
  experts on the CPU is ``cpu_experts``; any other llama.cpp is ``llamacpp``.
  Each judged field has its own percents, which :mod:`mcgyvr.derived`
  answers: the user's own ``numbers.yaml`` first, else the product's shipped
  estimates (``data/numbers.json``). The lab's measured percents are recorded
  in ``tools/runs/derived.json``, which :mod:`mcgyvr.derived` does not read;
  a lab test judges with them, from the user's file
  (``tests/lab_numbers.py``): warm decode those of
  ``records/measurements/fleet-identity-2026-09-11/tolerances.json``, prefill
  its own, from
  ``records/measurements/fleet-identity-prefill-2026-09-12/results-prefill.json``
  (``tests/test_prefill_is_judged_by_its_own_measured_class_tolerance.py``).
  The lock's NVMe baseline check reads the same class.
* **The lock's plain values are judged.** Decode and prefill each fall below by
  their own class percent. Card memory rises above the unit's ``room_mib``.
  Restarts are exactly 0.
* **Card and restarts are read through the door** by that same read; a rig is
  reached only behind the door (``tests/test_one_door.py``). Without a read the
  probe names both as not read, with that reason, rather than reaching a rig by
  another way.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests import lab_numbers

REPO = Path(__file__).resolve().parent.parent
HARNESS = REPO / "records" / "measurements" / "fleet-setup-2026-09-13"
VLLM_HARNESS = HARNESS / "srv2" / "measure_vllm.py"
LLAMA_HARNESS = HARNESS / "srv1" / "harness_llama.py"

UNIT_3B = "unt-" + "5" * 64
UNIT_DS = "unt-" + "e" * 64
RIG1 = "rig-" + "0" * 64
RIG2 = "rig-" + "c" * 64
CLASSES = {"vllm": 1.0, "llamacpp": 1.0, "cpu_experts": 48.0}
TOLERANCES: dict[str, Any] = {"warm_decode_class_pct": CLASSES}

FLEET: dict[str, Any] = {
    "profile": "live",
    "units": {
        "srv2_3b": {
            "rig": "srv2",
            "unit_id": UNIT_3B,
            "address": "http://srv2:8001",
            "engine": "vllm",
            "model": "Qwen/Qwen2.5-Coder-3B-Instruct-AWQ",
            "width": 8,
            "window": 4096,
            "output_tokens": 2048,
            "request_timeout_s": 180,
            "room_mib": 3573,
            "kv_cache_memory_bytes": 1207959552,
            "attention_backend": "FLASH_ATTN",
            "container": "mcgyvr-srv2-3b",
        },
        "srv1_deepseek": {
            "rig": "srv1",
            "unit_id": UNIT_DS,
            "address": "http://srv1:8080",
            "engine": "llama.cpp",
            "model": "deepseek-coder-v2-16b",
            "width": 2,
            "window": 8192,
            "output_tokens": 2048,
            "request_timeout_s": 180,
            "room_mib": 5458,
            "launch": {"n_cpu_moe": 19, "flags": ["-c", "8192", "-ngl", "99"]},
        },
    },
    "rigs": {"srv1": {"rig_id": RIG1}, "srv2": {"rig_id": RIG2}},
    "fleets": {
        "b-small": {
            "layout": {
                "srv2": [["srv2_3b", "awake"]],
                "srv1": [["srv1_deepseek", "awake"]],
            },
            "next": [],
        }
    },
}

EVIDENCE: dict[str, Any] = {
    "rigs": {"srv1": {"card_mib": 6144}, "srv2": {"card_mib": 12288}},
    "combinations": [
        {
            "rig": "srv2",
            "slots": [["srv2_3b", "awake"]],
            "passed": True,
            "overhead_mib": 610.5,
            "restarts": {"srv2_3b": 0},
            "warm_decode_tok_s": {"srv2_3b": 126.7},
            "prefill_tok_s": {"srv2_3b": 11500.0},
            "attention_backend": {"srv2_3b": "FLASH_ATTN"},
            "validated_at": "2026-09-13T21:44:00Z",
            "envelope": "records/measurements/fleet-setup-2026-09-13/srv2",
        },
        {
            "rig": "srv1",
            "slots": [["srv1_deepseek", "awake"]],
            "passed": True,
            "overhead_mib": 486.22,
            "restarts": {"srv1_deepseek": 0},
            "warm_decode_tok_s": {"srv1_deepseek": 32.56},
            "prefill_tok_s": {"srv1_deepseek": 307.11},
            "card_peak_mib": {"srv1_deepseek": 5458},
            "card_steady_mib": {"srv1_deepseek": 5430},
            "validated_at": "2026-09-13T21:48:11Z",
            "envelope": "records/measurements/fleet-setup-2026-09-13/srv1",
        },
    ],
    "moves": [],
}

NOW = datetime(2026, 9, 15, 12, 0, 0, tzinfo=UTC)


def _harness_strings(path: Path) -> dict[str, Any]:
    """The module-level string constants a harness assigns, evaluated as written."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        expr = ast.Expression(node.value)
        ast.fix_missing_locations(expr)
        try:
            value = eval(
                compile(expr, str(path), "eval"),
                {"__builtins__": {}},
                dict(found),
            )
        except Exception:
            continue
        found[target.id] = value
    return {k: v for k, v in found.items() if isinstance(v, str | list)}


def live_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fleet: dict[str, Any] = FLEET,
    evidence: dict[str, Any] = EVIDENCE,
) -> Path:
    """A HOME holding one promoted fleet, named live, with its journal in tmp.

    It holds the lab's recorded numbers as the user's own, as every lab
    test's HOME does (``tests/lab_numbers.py``).
    """
    from mcgyvr.fleet import lock

    home = tmp_path / "home"
    folder = home / ".mcgyvr" / "fleets" / "b-small"
    folder.mkdir(parents=True)
    (folder / "fleet.yaml").write_text(yaml.safe_dump(fleet), encoding="utf-8")
    journal = tmp_path / "journal"
    policy = {
        "ladder": ["srv2_3b", "srv1_deepseek"],
        "journal": {"dir": str(journal)},
    }
    (folder / "policy.yaml").write_text(yaml.safe_dump(policy), encoding="utf-8")
    lock.write(folder, fleet, evidence, tolerances=TOLERANCES)
    (home / ".mcgyvr" / "live.json").write_text(
        json.dumps({"fleet": "b-small", "since": "2026-09-15T00:00:00Z"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("MCGYVR_CONFIG", raising=False)
    lab_numbers.write()
    monkeypatch.chdir(tmp_path)
    return journal


class FakeUnits:
    """Both engines' HTTP faces, answering at the rates the test sets.

    The clock moves only inside a request, by the seconds the answer took, so
    a vLLM rate is exactly what ``completion_tokens`` over the wall gives.
    """

    def __init__(self, rates: Mapping[str, float]) -> None:
        self.rates = dict(rates)
        self.now = 1000.0
        self.posts: list[tuple[str, dict[str, Any]]] = []

    def clock(self) -> float:
        return self.now

    def get(self, url: str, timeout: float) -> dict[str, Any]:
        assert url == "http://srv2:8001/v1/models", url
        return {"data": [{"id": "Qwen/Qwen2.5-Coder-3B-Instruct-AWQ"}]}

    def post(self, url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        self.posts.append((url, payload))
        if url.startswith("http://srv2:8001"):
            if payload["max_tokens"] == 256:
                self.now += 256 / self.rates["3b_decode"]
                return {"usage": {"completion_tokens": 256, "prompt_tokens": 20}}
            if payload["max_tokens"] == 16:
                self.now += 1960 / self.rates["3b_prefill"]
                return {"usage": {"completion_tokens": 16, "prompt_tokens": 1960}}
            self.now += 0.5
            return {"usage": {"completion_tokens": 64, "prompt_tokens": 20}}
        assert url == "http://srv1:8080/completion", url
        if payload["n_predict"] == 256:
            return {"timings": {"predicted_per_second": self.rates["ds_decode"]}}
        if payload["n_predict"] == 16:
            return {"timings": {"prompt_per_second": self.rates["ds_prefill"]}}
        return {"timings": {"predicted_per_second": 1.0}}


def idle(*_: Any) -> int:
    return 0


def run_probe(
    fake: FakeUnits,
    in_flight: Callable[[str, Mapping[str, Any]], int | None] = idle,
    units: list[str] | None = None,
) -> Any:
    from mcgyvr.fleet import probe

    return probe.run(
        transport=fake,
        in_flight=in_flight,
        clock=fake.clock,
        units=units,
        now=NOW,
    )


def rows(journal: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for path in sorted(journal.rglob("*.jsonl"))
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


HOLDING = {"3b_decode": 126.7, "3b_prefill": 11500.0, "ds_decode": 32.56}
HOLDING |= {"ds_prefill": 307.11}


# --- the tolerance class ----------------------------------------------------


def test_the_class_tolerances_are_the_measured_ones_stated_in_derived_json() -> None:
    measured = json.loads(
        (
            REPO / "records/measurements/fleet-identity-2026-09-11/tolerances.json"
        ).read_text(encoding="utf-8")
    )["classes"]
    stated = lab_numbers.class_tolerances()["warm_decode_tok_s"]
    assert {name: stated[name] for name in measured} == {
        name: float(body["tolerance_pct"]) for name, body in measured.items()
    }
    # ``mtp`` was measured later, by the mtp-ornith window (owner, 2026-09-16).
    assert set(stated) - set(measured) == {"mtp"}


# --- judging the lock's plain values ----------------------------------------

STAMP = {
    "fleet": "b-small",
    "rig": "srv1",
    "rig_id": RIG1,
    "combination_id": "cmb-" + "a" * 64,
    "unit_id": UNIT_DS,
}
PLAIN = {
    UNIT_DS: {
        "warm_decode_tok_s": 32.56,
        "prefill_tok_s": 307.11,
        "card_peak_mib": 5458,
        "tolerance_pct": {"warm_decode_tok_s": 48.0, "prefill_tok_s": 1.0},
        "room_mib": 5458,
    }
}


def judged(field: str, value: float, tmp_path: Path) -> list[dict[str, Any]]:
    from mcgyvr.fleet import alerts

    return list(
        alerts.check(
            [{"unit_id": UNIT_DS, "field": field, "observed": value}],
            approved=PLAIN,
            profile="live",
            journal_dir=tmp_path / field,
            stamp=STAMP,
            run_id="run-20260915T120000-0a1b2c3d",
            lease_id="probe-0a1b2c3d",
        )
    )


# --- the probe --------------------------------------------------------------


def test_the_probe_sends_the_locks_own_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    live_home(tmp_path, monkeypatch)
    fake = FakeUnits(HOLDING)
    run_probe(fake)

    vllm = _harness_strings(VLLM_HARNESS)
    llama = _harness_strings(LLAMA_HARNESS)
    to_3b = [p for u, p in fake.posts if u.startswith("http://srv2:8001")]
    assert [p["max_tokens"] for p in to_3b] == [64] + [256] * 5 + [16] * 3
    assert all(p["temperature"] == 0 for p in to_3b)
    assert [p["ignore_eos"] for p in to_3b] == [False] + [True] * 5 + [False] * 3
    assert all(p["messages"] == vllm["SHORT"] for p in to_3b[:6])
    assert all(
        p["messages"] == [{"role": "user", "content": vllm["LONG"]}] for p in to_3b[6:]
    )
    assert all(p["model"] == "Qwen/Qwen2.5-Coder-3B-Instruct-AWQ" for p in to_3b)

    to_ds = [p for u, p in fake.posts if u.startswith("http://srv1:8080")]
    assert [p["n_predict"] for p in to_ds] == [64] + [256] * 5 + [16] * 3
    assert all(p["temperature"] == 0 for p in to_ds)
    assert all(p["prompt"] == llama["SHORT_PROMPT"] for p in to_ds[:6])
    assert all(p["prompt"] == llama["LONG_PROMPT"] for p in to_ds[6:])
    assert all(p.get("cache_prompt") is False for p in to_ds[1:])


def lock_root(tmp_path: Path) -> Path:
    """The live fleet folder :func:`live_home` promoted, which holds its locks."""
    return tmp_path / "home" / ".mcgyvr" / "fleets" / "b-small"


# --- the command line -------------------------------------------------------

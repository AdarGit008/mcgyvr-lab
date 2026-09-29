# The lab's part of a split test file. The tests of this file that are the
# product's were removed here; they remain in the product's file at this path.
"""An attempt row records how fast the unit answered, and how busy the unit was.

Owner ruling F2: live must write "the record of speed and memory (and
anything else we need for tolerance check) to the journal", on every dispatch:
decode tok/s, prefill tok/s and the requests in flight, so a live observation
can be judged against a locked unit's ``warm_decode_tok_s`` and
``prefill_tok_s`` — and judged only when one request was in flight.

"In flight" is the unit's fact, not this process's. Separate ``mcgyvr run``
processes dispatch to one unit at once, and a count kept per process would call
every one of them solo. So the count is read
off the unit itself, immediately before and immediately after the dispatch,
and the larger reading is kept:

* ``in_flight`` — on a llama.cpp unit, the ``/slots`` entries that are
  ``is_processing``; on a vLLM unit, ``vllm:num_requests_running`` plus
  ``vllm:num_requests_waiting`` from ``/metrics``. Either way this request is
  counted. ``in_flight_source`` says which (``slots`` | ``vllm_metrics``). A
  read that fails leaves both out of the row — a process-local count is never
  written under that name.
* ``decode_tok_s`` — llama.cpp's own ``timings.predicted_per_second``
  (``decode_source: timings``); otherwise ``completion_tokens / latency_s``
  (``usage_latency``), the formula the vLLM units' lock was measured with.
* ``prefill_tok_s`` — llama.cpp's ``timings.prompt_per_second`` (``timings``);
  on vLLM, ``prompt_tokens`` over the ``vllm:time_to_first_token_seconds_sum``
  delta (``metrics_ttft``), only when the unit read 1 at both reads and the
  histogram count moved by exactly one.

Which page is read follows the unit's declared engine: a llama.cpp unit is
asked for no ``/metrics`` (llama-server answers it 501 unless started with
``--metrics``), a vLLM unit for no ``/slots``, and a keyed endpoint — a hosted
provider — for neither.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

from mcgyvr.pool import Endpoint, Protocol

REPO = Path(__file__).resolve().parent.parent


TTFT = "vllm:time_to_first_token_seconds"


def endpoint(engine: str | None, *, key: str | None = None) -> Endpoint:
    return Endpoint(
        source="unit",
        base_url="http://localhost:8080",
        protocol=Protocol.OPENAI,
        max_parallel=2,
        credential_env=key,
        engine=engine,
    )


def answer(
    *,
    prompt_tokens: int = 2015,
    completion_tokens: int = 256,
    timings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A chat-completions answer; ``timings`` is what llama-server adds."""
    document: dict[str, Any] = {
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "x = 1\n"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    }
    if timings is not None:
        document["timings"] = timings
    return document


def metrics(
    *, ttft_sum: float = 1.0, ttft_count: int = 10, running: int = 0, waiting: int = 0
) -> str:
    """A vLLM ``/metrics`` page, in its Prometheus shape with labels."""
    labels = '{engine="0",model_name="/root/.cache/huggingface/hub/m"}'
    return (
        f"# HELP {TTFT} Histogram of time to first token in seconds.\n"
        f"# TYPE {TTFT} histogram\n"
        f"{TTFT}_sum{labels} {ttft_sum}\n"
        f"{TTFT}_count{labels} {ttft_count}\n"
        f"vllm:num_requests_running{labels} {float(running)}\n"
        f"vllm:num_requests_waiting{labels} {float(waiting)}\n"
    )


def slots(processing: int, total: int = 2) -> str:
    """A llama-server ``/slots`` answer with ``processing`` slots busy."""
    return json.dumps(
        [{"id": i, "is_processing": i < processing} for i in range(total)]
    )


# --- decode and prefill, read from the reply ---------------------------------


# --- in flight: the unit's own count -----------------------------------------


# --- the vLLM prefill, which only a solo dispatch permits --------------------


# --- the row, and the index over it ------------------------------------------


def _index() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        "live_index_for_rates", REPO / "tools" / "live" / "index.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_journal_index_has_a_column_for_each_new_field() -> None:
    columns = dict(_index().COLUMNS)

    assert columns.get("decode_tok_s") == "REAL"
    assert columns.get("decode_source") == "TEXT"
    assert columns.get("prefill_tok_s") == "REAL"
    assert columns.get("prefill_source") == "TEXT"
    assert columns.get("in_flight") == "INTEGER"
    assert columns.get("in_flight_source") == "TEXT"

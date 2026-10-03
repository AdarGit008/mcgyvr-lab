"""`@stagger=S` sends request i of a level S x i seconds after the level opens.

A level's requests all started together, which is the best case for batching
over RPC: every slot prefills at once and then only decodes. Real traffic
arrives spread out, so one slot prefills while the others decode, and the
split KV then breaks the step into more ubatches (the desk read §Q4, item 2).
A staggered level is that load; arrival order is also what the held request's
FIFO is judged against (§Q2).
"""

from __future__ import annotations

import threading
import time

import pytest

from tools.runs.drivers import mgpu_cell as mc


def test_request_i_is_scheduled_at_i_times_the_stagger() -> None:
    cell = mc.parse_extra("@stagger=0.5")
    assert cell.stagger == 0.5
    assert [s.at for s in mc.schedule(3, cell)] == [0.0, 0.5, 1.0]
    assert [s.i for s in mc.schedule(3, cell)] == [0, 1, 2]


def test_without_a_stagger_every_request_starts_at_once() -> None:
    assert [s.at for s in mc.schedule(4, mc.parse_extra(""))] == [0.0] * 4


@pytest.mark.parametrize("raw", ["@stagger=-1", "@stagger=soon"])
def test_a_stagger_that_is_not_a_delay_is_refused(raw: str) -> None:
    with pytest.raises(ValueError):
        mc.parse_extra(raw)


def test_the_runner_starts_each_request_no_earlier_than_its_offset() -> None:
    plan = mc.schedule(3, mc.parse_extra("@stagger=0.2"))
    started: dict[int, float] = {}
    lock = threading.Lock()

    def one(sent: mc.Sent) -> int:
        with lock:
            started[sent.i] = time.monotonic()
        return sent.i * 10

    t0 = time.monotonic()
    got = mc.launch(plan, one)
    assert got == [0, 10, 20]
    offsets = [started[i] - t0 for i in range(3)]
    assert offsets[1] >= 0.2 - 0.01
    assert offsets[2] >= 0.4 - 0.01
    assert offsets[0] < offsets[1] < offsets[2]


def test_a_request_that_raises_leaves_its_place_empty() -> None:
    def one(sent: mc.Sent) -> int:
        if sent.i == 1:
            raise RuntimeError("thread died")
        return sent.i

    assert mc.launch(mc.schedule(3, mc.parse_extra("")), one) == [0, None, 2]

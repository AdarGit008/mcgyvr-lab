"""`@np=K` pins the head's slots, whatever concurrency the cell offers it.

The two-card sweep launched llama.cpp with `-np` equal to the widest level, so a
one-slot head could never be offered two or four requests at once: the cell
that stands for today's pooled head (`-np 1`) did not exist. Issue #46 step 1
(`records/plans/hub-batching-2026-10-02.md` §4) needs every arm to run the same
levels `1,2,4` with the slot count pinned apart from them. An explicit `-np`
splits `-c` per slot (the desk read §Q1), so the pinned launch keeps the
per-slot window by asking for `-c = K x ctx`, and the engine's own
`n_seq_max` and `kv_unified` lines are read back beside the KV buffers.
"""

from __future__ import annotations

import pytest

from tools.runs.drivers import mgpu_cell as mc
from tools.runs.drivers import mgpu_read as rd


def test_np_pins_the_slots_whatever_the_levels() -> None:
    cell = mc.parse_extra("@np=1")
    assert cell.np == 1
    assert mc.engine_slots([1, 2, 4], cell, 2048) == (1, 2048)


def test_np_keeps_the_per_slot_window_by_multiplying_c() -> None:
    assert mc.engine_slots([1, 2, 4], mc.parse_extra("@np=2"), 2048) == (2, 4096)


def test_without_np_the_widest_level_is_still_the_slot_count() -> None:
    assert mc.engine_slots([1, 2, 4], mc.parse_extra(""), 2048) == (4, 8192)


def test_np_is_the_drivers_word_and_never_reaches_the_engine() -> None:
    cell = mc.parse_extra("--rpc+192.0.2.7:50052+@np=4+-kvu")
    assert cell.np == 4
    assert cell.extra == "--rpc 192.0.2.7:50052 -kvu"


@pytest.mark.parametrize("raw", ["@np=0", "@np=-1", "@np=two"])
def test_a_slot_count_that_is_not_a_positive_integer_is_refused(raw: str) -> None:
    with pytest.raises(ValueError):
        mc.parse_extra(raw)


#: llama.cpp b10644's own context lines at -lv 4, as a split launch prints them.
LCP_SLOTS = """\
1.00.480.208 I llama_context: n_seq_max             = 4
1.00.480.208 I llama_context: n_ctx                 = 8192
1.00.480.209 I llama_context: n_ctx_seq             = 2048
1.00.480.210 I llama_context: kv_unified            = false
"""


def test_the_engine_says_how_many_slots_it_built_and_whether_they_share() -> None:
    got = rd.read_lcp(LCP_SLOTS)
    assert "n_seq_max=4" in got
    assert "kv_unified=false" in got
    assert "real_ctx_slot=2048" in got


def test_a_launch_log_without_the_slot_lines_reads_unread() -> None:
    got = rd.read_lcp("llama_context: n_ctx_seq = 2048\n")
    assert "n_seq_max=unread" in got
    assert "kv_unified=unread" in got

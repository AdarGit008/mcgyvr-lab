"""`@id_slot=a,b,...` names the slot each request of a level asks for.

llama.cpp's split KV batches only consecutive sequence ids into one ubatch (the
desk read §Q4, item 1), so busy slots 0 and 2 may cost two graphs a step where
0 and 1 cost one. Pricing that needs a cell whose requests name their slot
(`id_slot`, which the server honours on the chat endpoint) and a read-back of
the slot the server actually launched each task on, from its own log.
"""

from __future__ import annotations

import pytest

from tools.runs.drivers import mgpu_cell as mc
from tools.runs.drivers import mgpu_read as rd

MESSAGES = [{"role": "user", "content": "x"}]


def test_request_i_asks_for_the_ith_slot_named() -> None:
    cell = mc.parse_extra("@id_slot=0,2,1,3")
    assert cell.id_slot == (0, 2, 1, 3)
    assert [s.id_slot for s in mc.schedule(2, cell)] == [0, 2]
    assert [s.id_slot for s in mc.schedule(4, cell)] == [0, 2, 1, 3]
    assert [s.id_slot for s in mc.schedule(5, cell)] == [0, 2, 1, 3, 0]


def test_a_cell_that_names_no_slot_lets_the_server_choose() -> None:
    assert [s.id_slot for s in mc.schedule(3, mc.parse_extra(""))] == [
        None,
        None,
        None,
    ]


def test_the_slot_goes_into_the_request_body_only_when_named() -> None:
    named = mc.chat_body(MESSAGES, 64, engine="lcp", model="m", id_slot=2)
    assert named["id_slot"] == 2
    assert named["cache_prompt"] is True
    assert "model" not in named
    plain = mc.chat_body(MESSAGES, 64, engine="lcp", model="m")
    assert "id_slot" not in plain


def test_a_vllm_body_names_its_model_and_no_llamacpp_field() -> None:
    body = mc.chat_body(MESSAGES, 64, engine="vllm", model="org/m", ignore_eos=True)
    assert body["model"] == "org/m"
    assert body["ignore_eos"] is True
    assert "cache_prompt" not in body
    assert body["temperature"] == 0
    assert body["stream"] is True


@pytest.mark.parametrize("raw", ["@id_slot=", "@id_slot=0,x", "@id_slot=-1"])
def test_a_slot_list_that_is_not_slot_ids_is_refused(raw: str) -> None:
    with pytest.raises(ValueError):
        mc.parse_extra(raw)


#: llama.cpp b10644's SLT_INF lines (tools/server/server-common.h:25) at -lv 4.
SLOT_LOG = """\
1.37.193.205 I slot   load_model: id  0 | task -1 | new slot, n_ctx = 2048
2.01.000.001 I slot get_availabl: id  2 | task -1 | selected slot by id (2)
2.01.000.002 I slot launch_slot_: id  2 | task 7 | processing task, is_child = 0
2.01.000.003 I slot launch_slot_: id  0 | task 8 | processing task, is_child = 0
2.09.000.000 I slot      release: id  2 | task 7 | stop processing: n_tokens = 900
"""


def test_the_server_log_says_which_slot_each_task_was_launched_on() -> None:
    assert rd.slot_launches(SLOT_LOG) == [(2, 7), (0, 8)]
    assert rd.slot_launches("") == []

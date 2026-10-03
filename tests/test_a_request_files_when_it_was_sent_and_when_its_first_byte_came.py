"""Every request of a level is filed with its own clock, not only the level's.

The two-card sweep printed per-level medians, which cannot show a request the
engine held: at `-np 1` a second request waits in the server's queue and sees
no byte until its own first token (the desk read §Q2). Issue #46 step 1 reads
that silence, the start order and any 5xx from per-request rows: when the
request was sent, when the response's first byte came (the status line), its
first token, its end, its status and any error the stream carried.
"""

from __future__ import annotations

from tools.runs.drivers import mgpu_cell as mc


def _sse(*items: tuple[float, str]) -> list[tuple[float, bytes]]:
    return [(at, f"{line}\n".encode()) for at, line in items]


def test_the_first_token_is_the_first_delta_that_carries_one() -> None:
    got = mc.read_sse(
        _sse(
            (1.0, 'data: {"choices":[{"delta":{"role":"assistant"}}]}'),
            (1.5, 'data: {"choices":[{"delta":{"content":"def"}}]}'),
            (2.0, 'data: {"choices":[{"delta":{"content":" f"}}]}'),
            (2.1, 'data: {"choices":[],"usage":{"completion_tokens":2}}'),
            (2.2, "data: [DONE]"),
        ),
        t0=0.5,
    )
    assert got.first == 1.5
    assert got.last == 2.0
    assert got.chunks == 2
    assert got.usage == {"completion_tokens": 2}
    assert got.usage_at == 2.1
    assert got.error == ""


def test_an_error_the_stream_carries_is_kept_not_swallowed() -> None:
    got = mc.read_sse(
        _sse(
            (1.5, 'data: {"choices":[{"delta":{"content":"x"}}]}'),
            (3.0, 'data: {"error":{"code":500,"message":"ctx\\tfull"}}'),
        ),
        t0=0.0,
    )
    assert got.chunks == 1
    assert got.error == "ctx full"
    assert "\t" not in got.error


def test_a_request_row_gives_every_time_from_the_levels_start() -> None:
    sent = mc.Sent(i=1, at=0.5, id_slot=2)
    sent.send, sent.byte, sent.tok, sent.end = 10.5, 14.25, 14.25, 20.0
    sent.gen, sent.ptok, sent.want, sent.status = 130, 640, 130, "200"
    fields = mc.req_fields(sent, level_t0=10.0, level=2)
    assert fields[:2] == ["n=2", "i=1"]
    for want in (
        "send=0.500",
        "byte=4.250",
        "tok=4.250",
        "end=10.000",
        "gen=130",
        "ptok=640",
        "want=130",
        "id_slot=2",
        "status=200",
    ):
        assert want in fields


def test_a_request_that_never_answered_reads_unread_and_says_why() -> None:
    sent = mc.Sent(i=0, at=0.0, id_slot=None)
    sent.send, sent.end, sent.status, sent.err = 3.0, 4.0, "503", "Service\tUnavailable"
    fields = mc.req_fields(sent, level_t0=3.0, level=1)
    assert "byte=unread" in fields
    assert "tok=unread" in fields
    assert "id_slot=-" in fields
    assert "status=503" in fields
    assert "err=Service Unavailable" in fields
    assert all("\t" not in f for f in fields)

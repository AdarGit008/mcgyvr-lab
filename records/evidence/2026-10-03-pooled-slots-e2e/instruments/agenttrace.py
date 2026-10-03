#!/usr/bin/env python3
"""Run the rig agent (``mcgyvr rig ...``) with timestamps on its relays.

    AGENTTRACE_FILE=trace.jsonl <product venv>/bin/python agenttrace.py rig run

The agent under test (mcgyvr ``rig-head-slots`` @ abccb902) prints nothing per
relay, so this wraps the relay path of ``mcgyvr.rig.relay`` and appends one
JSON line per event (``t`` is ``time.time()`` on the rig):

- ``a_request``   ``Relays.request``: a ``relay_request`` from the hub, and
  whether it was taken or answered at once (``busy`` and the like).
- ``a_head_req``  the agent's HTTP request to the head is sent.
- ``a_head_status``  the head's status line is read.
- ``a_first_chunk``  the first bytes of the head's answer reach the agent.
- ``a_first_token``  the first bytes that carry a non-empty ``"content"``
  delta (the first token, agent-side).
- ``a_frame``     a ``relay_response``, the first ``relay_data`` and the
  ``relay_end`` handed to the agent's outbox, which its pump sends to the hub.

Each wrapper calls the original and returns or raises what it does. The body
of a request or an answer is never written; only its arrival time, its byte
count and whether it carries a content delta.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import sys
import threading
import time
from typing import Any

from mcgyvr import cli
from mcgyvr.rig import relay as rr

_OUT = open(os.environ["AGENTTRACE_FILE"], "a", buffering=1)  # noqa: SIM115
_LOCK = threading.Lock()
_LOCAL = threading.local()
_CONTENT = re.compile(rb'"content":"[^"]')


def emit(ev: str, **fields: Any) -> None:
    line = json.dumps({"t": round(time.time(), 6), "ev": ev, **fields})
    with _LOCK:
        _OUT.write(line + "\n")


class TracedConnection(http.client.HTTPConnection):
    """An ``HTTPConnection`` that timestamps a relay's request to the head.

    It logs only inside a relay's thread (``_LOCAL.rid`` set); anywhere else
    it is the plain class."""

    def request(self, *args: Any, **kwargs: Any) -> None:
        super().request(*args, **kwargs)
        rid = getattr(_LOCAL, "rid", None)
        if rid is not None:
            emit("a_head_req", rid=rid)

    def getresponse(self) -> http.client.HTTPResponse:
        response = super().getresponse()
        rid = getattr(_LOCAL, "rid", None)
        if rid is None:
            return response
        emit("a_head_status", rid=rid, status=response.status)
        read1 = response.read1
        state = {"first": False, "token": False, "bytes": 0}

        def traced_read1(n: int = -1) -> bytes:
            chunk = read1(n)
            state["bytes"] += len(chunk)
            if chunk and not state["first"]:
                state["first"] = True
                emit("a_first_chunk", rid=rid, n=len(chunk))
            if chunk and not state["token"] and _CONTENT.search(chunk):
                state["token"] = True
                emit("a_first_token", rid=rid, at_bytes=state["bytes"])
            if not chunk:
                emit("a_head_eof", rid=rid, bytes=state["bytes"])
            return chunk

        response.read1 = traced_read1  # type: ignore[method-assign]
        return response


http.client.HTTPConnection = TracedConnection  # type: ignore[misc]

_request = rr.Relays.request


def request(self: Any, envelope: Any) -> str | None:
    rid = envelope.body.get("request_id")
    answer = _request(self, envelope)
    if answer is None:
        emit("a_request", rid=rid, taken=True, active=len(self._active))
    else:
        code = None
        try:
            code = json.loads(answer)["body"].get("error_code")
        except (ValueError, KeyError, TypeError, AttributeError):
            code = "unparsed"
        emit("a_request", rid=rid, taken=False, code=code, active=len(self._active))
    return answer


rr.Relays.request = request  # type: ignore[method-assign]

_relay = rr.Relays._relay


def relay(self: Any, one: Any) -> None:
    _LOCAL.rid = one.asked.request_id
    try:
        _relay(self, one)
    finally:
        _LOCAL.rid = None


rr.Relays._relay = relay  # type: ignore[method-assign]

_init = rr.Relays.__init__


def init(self: Any, *, send: Any, **kw: Any) -> None:
    def traced_send(text: str, *args: Any, **kwargs: Any) -> bool:
        kind = None
        if '"relay_response"' in text:
            kind = "response"
        elif '"relay_end"' in text:
            kind = "end"
        elif '"relay_data"' in text and '"seq":0' in text.replace(" ", ""):
            kind = "first_data"
        if kind is not None:
            try:
                body = json.loads(text)["body"]
                emit(
                    "a_frame",
                    rid=body.get("request_id"),
                    kind=kind,
                    outcome=body.get("outcome"),
                    code=body.get("error_code"),
                )
            except (ValueError, KeyError, TypeError):
                emit("a_frame", rid=None, kind=kind)
        sent: bool = send(text, *args, **kwargs)
        return sent

    _init(self, send=traced_send, **kw)


rr.Relays.__init__ = init  # type: ignore[method-assign]

if __name__ == "__main__":
    emit("agent_start", argv=sys.argv[1:], pid=os.getpid())
    raise SystemExit(cli.main(sys.argv[1:]))

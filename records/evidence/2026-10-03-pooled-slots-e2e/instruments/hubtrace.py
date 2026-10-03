#!/usr/bin/env python3
"""Run ``mcgyvr-hub`` with timestamps on the request path, nothing else changed.

    HUBTRACE_FILE=trace.jsonl <hub venv>/bin/python hubtrace.py serve --host ... --port ... --db ...

The hub under test (mcgyvr-hub ``pool-head-slots`` @ 76cd212) logs nothing of
its own beyond uvicorn's access lines, so this wraps six of its functions and
appends one JSON line per event to ``$HUBTRACE_FILE`` (``t`` is ``time.time()``,
the same clock the load client on this host reads):

- ``start`` / ``start_end``   ``completions.start``: a chat request's own path
  (limits, lease, relay, the head's status line). ``tag`` is the request's
  ``seed``, which the load client sets unique per request.
- ``q_enter`` / ``q_exit``    ``PoolSessions._take_relay``: the wait for one of
  the session's relays, with its width, relays and queue length on entry, and
  how it ended (admitted, busy, cancelled).
- ``relay_free``              ``PoolSessions._give_relay`` on the lease's exit.
- ``relay_id``                ``AgentConnection.relay``: the request id the hub
  gave the relay, joining this trace to the agent's.
- ``frame``                   ``RelayStream.feed``: the head's status line and
  the first data frame as they reach the hub, and the relay's end (outcome and
  error code, e.g. ``busy``).
- ``head_start``              ``PoolSessions._head_start``: the plan the hub
  sends the head: slots, ctx per slot, devices in ``-dev`` order, tensor split.
- ``http_error``              ``api.openai._error``: every error answer of
  ``/v1``, the 499 for a client that hung up included (added after the q1
  cells, so the q1 hang-up has no such line; README).

Each wrapper calls the original and returns or raises what it does. Nothing of
a request's body or answer is read or written.
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import os
import sys
import threading
import time
from collections.abc import AsyncIterator
from typing import Any

from mcgyvr_hub import agents, cli, completions, pool_sessions
from mcgyvr_hub.api import openai as openai_api

_OUT = open(os.environ["HUBTRACE_FILE"], "a", buffering=1)  # noqa: SIM115
_LOCK = threading.Lock()
TAG: contextvars.ContextVar[int | None] = contextvars.ContextVar("tag", default=None)


def emit(ev: str, **fields: Any) -> None:
    line = json.dumps({"t": round(time.time(), 6), "ev": ev, **fields})
    with _LOCK:
        _OUT.write(line + "\n")


# --- completions.start --------------------------------------------------------------
_start = completions.start


async def start(ctx: Any, user_id: str, chat: Any, scope: Any = None) -> Any:
    TAG.set(chat.seed)
    emit("start", tag=chat.seed, user=user_id, max_tokens=chat.max_tokens)
    try:
        done = await _start(ctx, user_id, chat, scope)
    except completions.CompletionError as exc:
        emit(
            "start_end",
            tag=chat.seed,
            status=exc.status,
            code=exc.code,
            retry_after=exc.retry_after_s,
        )
        raise
    except BaseException as exc:
        emit("start_end", tag=chat.seed, status=None, code=type(exc).__name__)
        raise
    emit("start_end", tag=chat.seed, status=done.status, code=None)
    return done


completions.start = start

# --- PoolSessions._take_relay / _give_relay -----------------------------------------
PS = pool_sessions.PoolSessions
_take = PS._take_relay
_give = PS._give_relay


async def take_relay(self: Any, live: Any, user_id: str, wait_s: float) -> None:
    tag = TAG.get()
    t0 = time.time()
    emit(
        "q_enter",
        tag=tag,
        user=user_id,
        session=live.id,
        width=live.width,
        relays=live.relays,
        queued=len(live.queue),
        wait_s=wait_s,
    )
    try:
        await _take(self, live, user_id, wait_s)
    except pool_sessions.SessionError as exc:
        emit(
            "q_exit",
            tag=tag,
            outcome=str(getattr(exc, "code", "error")),
            waited=round(time.time() - t0, 6),
        )
        raise
    except BaseException as exc:
        emit(
            "q_exit",
            tag=tag,
            outcome=type(exc).__name__,
            waited=round(time.time() - t0, 6),
        )
        raise
    emit(
        "q_exit",
        tag=tag,
        outcome="admitted",
        waited=round(time.time() - t0, 6),
        relays=live.relays,
    )


def give_relay(self: Any, live: Any) -> None:
    emit("relay_free", tag=TAG.get(), session=live.id, relays_before=live.relays)
    _give(self, live)


PS._take_relay = take_relay  # type: ignore[method-assign]
PS._give_relay = give_relay  # type: ignore[method-assign]

# --- PoolSessions._head_start ---------------------------------------------------------
_head_start = PS._head_start


def head_start(self: Any, live: Any, ports: Any) -> Any:
    plan = live.plan
    emit(
        "head_start",
        session=live.id,
        model=plan.model,
        slots=plan.slots,
        width=live.width,
        ctx=plan.ctx,
        max_ctx=plan.max_ctx,
        head_rig=plan.head_rig_id,
        workers=list(plan.worker_rig_ids),
        devices=[[d.kind, d.rig_id, d.card_index] for d in plan.devices],
        tensor_split=list(plan.tensor_split),
    )
    return _head_start(self, live, ports)


PS._head_start = head_start  # type: ignore[method-assign]

# --- AgentConnection.relay / RelayStream.feed ----------------------------------------
_relay = agents.AgentConnection.relay


@contextlib.asynccontextmanager
async def relay(self: Any, **kw: Any) -> AsyncIterator[Any]:
    async with _relay(self, **kw) as stream:
        emit("relay_id", tag=TAG.get(), rid=stream.request_id, rig=self.rig_id)
        yield stream


agents.AgentConnection.relay = relay  # type: ignore[method-assign,assignment]

_feed = agents.RelayStream.feed
_seen: set[str] = set()


def feed(self: Any, message: Any) -> None:
    body = message.body
    if isinstance(message, agents.protocol.RelayResponse):
        emit("frame", rid=self.request_id, kind="response", status=body.status)
    elif isinstance(message, agents.protocol.RelayData):
        if self.request_id not in _seen:
            _seen.add(self.request_id)
            emit("frame", rid=self.request_id, kind="first_data", seq=body.seq)
    elif isinstance(message, agents.protocol.RelayEnd):
        _seen.discard(self.request_id)
        emit(
            "frame",
            rid=self.request_id,
            kind="end",
            outcome=body.outcome,
            code=body.error_code,
        )
    _feed(self, message)


agents.RelayStream.feed = feed  # type: ignore[method-assign]

# --- api.openai._error -----------------------------------------------------------------
# Every error answer of /v1 is built here, the 499 for a client that hung up
# included; uvicorn logs no access line for a response its client never got.
_error = openai_api._error


def error(status: int, code: str, message: str, **kw: Any) -> Any:
    emit("http_error", tag=TAG.get(), status=status, code=code)
    return _error(status, code, message, **kw)


openai_api._error = error

if __name__ == "__main__":
    emit("hub_start", argv=sys.argv[1:], pid=os.getpid())
    raise SystemExit(cli.main(sys.argv[1:]))

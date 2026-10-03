"""What one mgpu_sweep cell sends: its directives, its slots, each request.

Pure, so a test can hold it: mgpu_sweep.py refuses to import outside the door.

  parse_extra    a cell's extra split into the engine's words and the driver's
                 `@` directives (the list is mgpu_sweep.py's docstring)
  engine_slots   the `-np` and `-c` a cell launches with: `@np=K` pins K, else
                 the widest level; `-c` is always slots x the per-slot window,
                 because an explicit `-np` splits `-c` per slot
  schedule       request i of a level: when it is sent (`@stagger`) and which
                 slot it asks for (`@id_slot`)
  chat_body      the chat-completions body, `id_slot` only when named
  read_sse       a streamed reply read from (arrival time, raw line) pairs
  launch         a level's requests on threads, each at its own offset
  req_fields     one request's REQ row, every time from the level's start
"""

from __future__ import annotations

import json
import re
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from tools.runs.drivers import mgpu_read as rd

#: An error text is cut to this many characters on a REQ row.
ERR_CHARS = 200


@dataclass
class Cell:
    """A cell's extra split into the engine's words and this driver's directives."""

    extra: str = ""
    env: dict[str, str] = field(default_factory=dict)
    cpuset: str = ""
    headroom: int = 0
    prefill: int = 0
    knob: bool = False
    #: `@np=K`: the engine's slots, apart from the levels. 0 = the widest level.
    np: int = 0
    #: `@id_slot=a,b,...`: request i of a level asks for id_slot[i % len].
    id_slot: tuple[int, ...] = ()
    #: `@stagger=S`: request i of a level is sent S x i seconds after it opens.
    stagger: float = 0.0


def _positive(word: str, value: str) -> int:
    if not re.fullmatch(r"[0-9]+", value) or int(value) < 1:
        raise ValueError(f"{word} wants a positive integer, got {value!r}")
    return int(value)


def parse_extra(raw: str) -> Cell:
    c = Cell()
    words: list[str] = []
    for w in raw.replace("+", " ").split():
        if not w.startswith("@"):
            words.append(w)
        elif w == "@knob":
            c.knob = True
        elif w.startswith("@cpuset="):
            c.cpuset = w.split("=", 1)[1]
        elif w.startswith("@headroom="):
            c.headroom = int(w.split("=", 1)[1])
        elif w.startswith("@prefill="):
            c.prefill = int(w.split("=", 1)[1])
        elif w.startswith("@np="):
            c.np = _positive("@np", w.split("=", 1)[1])
        elif w.startswith("@id_slot="):
            ids = w.split("=", 1)[1].split(",")
            if not all(re.fullmatch(r"[0-9]+", i) for i in ids):
                raise ValueError(f"@id_slot wants slot ids a,b,..., got {w!r}")
            c.id_slot = tuple(int(i) for i in ids)
        elif w.startswith("@stagger="):
            value = w.split("=", 1)[1]
            try:
                c.stagger = float(value)
            except ValueError:
                raise ValueError(f"@stagger wants seconds, got {value!r}") from None
            if c.stagger < 0:
                raise ValueError(f"@stagger wants seconds >= 0, got {value!r}")
        elif re.fullmatch(r"@[A-Z][A-Z0-9_]*=\S*", w):
            k, v = w[1:].split("=", 1)
            c.env[k] = v
        else:
            raise ValueError(f"unknown directive {w!r}")
    c.extra = " ".join(words)
    return c


def engine_slots(levels: list[int], cell: Cell, ctx: int) -> tuple[int, int]:
    """``(-np, -c)``: ``@np`` or the widest level, and slots x the window."""
    np_ = cell.np or max(levels)
    return np_, np_ * ctx


@dataclass
class Sent:
    """One request of a level: its plan, then its clock (absolute seconds)."""

    i: int
    at: float
    id_slot: int | None
    send: float | None = None
    byte: float | None = None
    tok: float | None = None
    end: float | None = None
    gen: int = 0
    ptok: int = 0
    want: int = 0
    status: str = ""
    err: str = ""


def schedule(n: int, cell: Cell) -> list[Sent]:
    ids = cell.id_slot
    return [
        Sent(i=i, at=i * cell.stagger, id_slot=ids[i % len(ids)] if ids else None)
        for i in range(n)
    ]


def chat_body(
    messages: list[dict[str, str]],
    want: int,
    *,
    engine: str,
    model: str,
    ignore_eos: bool = False,
    id_slot: int | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {
        "messages": messages,
        "max_tokens": want,
        "temperature": 0,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if ignore_eos:
        body["ignore_eos"] = True
    if engine == "vllm":
        body["model"] = model
    else:
        body["cache_prompt"] = True
    if id_slot is not None:
        body["id_slot"] = id_slot
    return body


@dataclass
class Streamed:
    """What a streamed reply said, and when (absolute seconds)."""

    first: float | None = None
    last: float = 0.0
    chunks: int = 0
    usage: dict[str, int] = field(default_factory=dict)
    usage_at: float | None = None
    error: str = ""


def one_line(text: str, width: int = ERR_CHARS) -> str:
    return " ".join(text.split())[:width]


def read_sse(lines: Iterable[tuple[float, bytes]], t0: float) -> Streamed:
    """A token is a delta in any field of rd.TOKEN_FIELDS; an ``error`` event
    (llama.cpp's mid-stream failure) is kept as text."""
    s = Streamed(last=t0)
    for at, raw in lines:
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:") or line == "data: [DONE]":
            continue
        d = json.loads(line[5:])
        if d.get("error"):
            err = d["error"]
            text = err.get("message", json.dumps(err)) if isinstance(err, dict) else err
            s.error = one_line(str(text))
            continue
        if d.get("usage"):
            s.usage = d["usage"]
            s.usage_at = at
        for choice in d.get("choices") or []:
            if rd.streamed_token(choice.get("delta") or {}):
                s.first = at if s.first is None else s.first
                s.last = at
                s.chunks += 1
    return s


def launch[T](plan: list[Sent], one: Callable[[Sent], T]) -> list[T | None]:
    """Each request on its own thread, started no earlier than ``at`` seconds
    after the level opens. A place still ``None`` is a thread that died."""
    out: list[T | None] = [None] * len(plan)
    t0 = time.monotonic()

    def run(sent: Sent) -> None:
        wait = t0 + sent.at - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            out[sent.i] = one(sent)
        except Exception:  # a dead request is an empty place
            out[sent.i] = None

    threads = [threading.Thread(target=run, args=(s,)) for s in plan]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return out


def _rel(t: float | None, t0: float) -> str:
    return "unread" if t is None else f"{t - t0:.3f}"


def req_fields(sent: Sent, level_t0: float, level: int) -> list[str]:
    out = [
        f"n={level}",
        f"i={sent.i}",
        f"send={_rel(sent.send, level_t0)}",
        f"byte={_rel(sent.byte, level_t0)}",
        f"tok={_rel(sent.tok, level_t0)}",
        f"end={_rel(sent.end, level_t0)}",
        f"gen={sent.gen}",
        f"ptok={sent.ptok}",
        f"want={sent.want}",
        f"id_slot={'-' if sent.id_slot is None else sent.id_slot}",
        f"status={sent.status or 'unread'}",
    ]
    if sent.err:
        out.append(f"err={one_line(sent.err)}")
    return out

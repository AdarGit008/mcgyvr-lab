#!/usr/bin/env python3
"""records/evidence/2026-10-01-rpc-split/instruments/rpcwire.py — a counting, delaying relay
between llama.cpp's RPC client and a ggml-rpc-server. Stdlib only; it is
shipped to the head rig and run there with ``python3 -``.

    python3 rpcwire.py LISTEN_HOST:PORT UPSTREAM_HOST:PORT CTL_JSON STATS_JSON

What it measures. The client's stream is parsed at the protocol's framing
(``cmd u8 | size u64 | payload``, ggml-rpc.cpp ``send_rpc_cmd``), so every
command is counted by name with its bytes; the server's stream is counted in
bytes. Commands that wait for a reply (GET_TENSOR, SET_TENSOR_HASH,
COPY_TENSOR, HELLO, ALLOC_BUFFER, ...) are the round trips; SET_TENSOR,
GRAPH_COMPUTE and GRAPH_RECOMPUTE are sent without one. Totals are written to
STATS_JSON twice a second; a reader diffs two snapshots.

What it emulates. CTL_JSON is re-read twice a second: ``{"rtt_ms": R,
"mbit": B}`` holds every chunk for R/2 ms in each direction and serialises it
at B Mbit/s (0 = unlimited). Order is preserved. This is a userspace stand-in
for a longer path, not netem: it adds no loss, no jitter and no TCP
congestion behaviour, and the relay itself costs a little latency, measured
as the R=0 arm.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import struct
import sys
import time
from typing import Any

CMDS = [
    "ALLOC_BUFFER",
    "GET_ALIGNMENT",
    "GET_MAX_SIZE",
    "BUFFER_GET_BASE",
    "FREE_BUFFER",
    "BUFFER_CLEAR",
    "SET_TENSOR",
    "SET_TENSOR_HASH",
    "GET_TENSOR",
    "COPY_TENSOR",
    "GRAPH_COMPUTE",
    "GET_DEVICE_MEMORY",
    "INIT_TENSOR",
    "GET_ALLOC_SIZE",
    "HELLO",
    "DEVICE_COUNT",
    "GRAPH_RECOMPUTE",
    "MEMSET_TENSOR",
    "NONE",
]

ctl = {"rtt_ms": 0.0, "mbit": 0.0}
stats: dict[str, Any] = {
    "c2s_bytes": 0,
    "s2c_bytes": 0,
    "c2s_chunks": 0,
    "s2c_chunks": 0,
    "conns": 0,
    "desync": 0,
    "cmd_n": {},
    "cmd_bytes": {},
}


class Parser:
    """Client->server framing: 1 byte cmd, u64 size, payload."""

    def __init__(self) -> None:
        self.buf = b""
        self.need_payload = 0
        self.cmd = None

    def feed(self, data: bytes) -> None:
        if self.need_payload:
            take = min(self.need_payload, len(data))
            self.need_payload -= take
            data = data[take:]
        self.buf += data
        while not self.need_payload and len(self.buf) >= 9:
            cmd = self.buf[0]
            (size,) = struct.unpack("<Q", self.buf[1:9])
            name = CMDS[cmd] if cmd < len(CMDS) else f"?{cmd}"
            if cmd >= len(CMDS):
                stats["desync"] += 1
            stats["cmd_n"][name] = stats["cmd_n"].get(name, 0) + 1
            stats["cmd_bytes"][name] = stats["cmd_bytes"].get(name, 0) + 9 + size
            rest = self.buf[9:]
            take = min(size, len(rest))
            self.buf = rest[take:]
            self.need_payload = size - take


async def pump(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    direction: str,
    parser: Parser | None,
) -> None:
    q: asyncio.Queue[tuple[float, bytes | None]] = asyncio.Queue()

    async def send() -> None:
        free_at = 0.0
        while True:
            due, data = await q.get()
            if data is None:
                break
            now = time.monotonic()
            if due > now:
                await asyncio.sleep(due - now)
            mbit = ctl.get("mbit") or 0
            if mbit:
                start = max(time.monotonic(), free_at)
                free_at = start + len(data) * 8 / (mbit * 1e6)
                await asyncio.sleep(max(0.0, free_at - time.monotonic()))
            writer.write(data)
            await writer.drain()
        writer.close()

    sender = asyncio.ensure_future(send())
    while True:
        data = await reader.read(1 << 20)
        if not data:
            break
        stats[f"{direction}_bytes"] += len(data)
        stats[f"{direction}_chunks"] += 1
        if parser:
            parser.feed(data)
        await q.put((time.monotonic() + ctl.get("rtt_ms", 0) / 2000.0, data))
    await q.put((0, None))
    await sender


async def handle(
    cr: asyncio.StreamReader, cw: asyncio.StreamWriter, upstream: tuple[str, int]
) -> None:
    stats["conns"] += 1
    sr, sw = await asyncio.open_connection(*upstream)
    for w in (cw, sw):
        s = w.get_extra_info("socket")
        if s is not None:
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    await asyncio.gather(
        pump(cr, sw, "c2s", Parser()), pump(sr, cw, "s2c", None), return_exceptions=True
    )


async def housekeeping(ctl_path: str, stats_path: str) -> None:
    while True:
        try:
            with open(ctl_path) as f:
                ctl.update(json.load(f))
        except (OSError, ValueError):
            pass
        stats["t"] = time.time()
        stats["ctl"] = dict(ctl)
        tmp = stats_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(stats, f)
        os.replace(tmp, stats_path)
        await asyncio.sleep(0.5)


async def main() -> None:
    listen, up, ctl_path, stats_path = sys.argv[1:5]
    lh, lp = listen.rsplit(":", 1)
    uh, upp = up.rsplit(":", 1)
    server = await asyncio.start_server(
        lambda r, w: handle(r, w, (uh, int(upp))), lh, int(lp)
    )
    keeper = asyncio.ensure_future(housekeeping(ctl_path, stats_path))
    async with server:
        await server.serve_forever()
    keeper.cancel()


if __name__ == "__main__":
    asyncio.run(main())

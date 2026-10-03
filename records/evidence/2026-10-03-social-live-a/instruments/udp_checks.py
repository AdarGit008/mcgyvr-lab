#!/usr/bin/env python3
"""UDP checks of the live hub's binding responder and embedded relay, from
outside the hub process (stdlib only; packet formats written from the hub's
protocol docstring, not imported).

Binding responder: a well-formed request with a token the hub never issued,
and a malformed one, must get no answer at all (positive answers need a token
the hub hands a rig: see agents_probe.py). Relay: tickets are minted here with
the hub's relay secret (read from the hub.env file, never printed):
bad ticket -> silence, expired -> refused(2), valid -> bound on a port of the
allocation range, packets forwarded between the two latched sides only,
oversized and third-party packets dropped, binds rate-limited per source.

    udp_checks.py --env HUB_ENV --target IP [--target IP ...] [--source IP ...]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import os
import socket
import struct
import time

STUN, RELAY = b"MCGS", b"MCGR"


def env_secret(path: str) -> bytes:
    for line in open(path):
        if line.startswith("MCGYVR_HUB_RELAY_SECRET="):
            return line.split("=", 1)[1].strip().encode()
    raise SystemExit("no relay secret in " + path)


def binding_request(token: bytes, txid: bytes, size: int = 64) -> bytes:
    head = STUN + bytes([1, 1]) + b"\0\0" + token + txid
    return head + bytes(size - len(head))


def ticket(secret: bytes, alloc: bytes, side: int, expires: int, max_mb: int) -> str:
    fields = struct.pack("!12sBII", alloc, side, max(expires, 0), max_mb)
    mac = hmac.new(hashlib.sha256(secret).digest(), b"mcgyvr-relay-v1" + fields, hashlib.sha256).digest()[:16]
    return base64.urlsafe_b64encode(fields + mac).decode().rstrip("=")


def relay_bind(t: str, size: int = 96) -> bytes:
    raw = t.encode()
    head = RELAY + bytes([1, 1]) + struct.pack("!H", len(raw)) + raw
    return head + bytes(size - len(head))


def parse_relay_answer(d: bytes) -> str:
    if len(d) == 8 and d[:4] == RELAY and d[5] == 2:
        return f"bound port={struct.unpack('!H', d[6:8])[0]}"
    if len(d) == 7 and d[:4] == RELAY and d[5] == 3:
        return f"refused reason={d[6]} ({ {1: 'bad_ticket', 2: 'expired', 3: 'full', 4: 'rate_limited'}.get(d[6], '?') })"
    return f"unparsed {d[:16]!r}"


def sock(src: str) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((src, 0))
    s.settimeout(1.0)
    return s


def ask(s: socket.socket, data: bytes, to: tuple[str, int]) -> bytes | None:
    s.sendto(data, to)
    try:
        return s.recvfrom(4096)[0]
    except TimeoutError:
        return None


def line(label: str, ok: bool, detail: str) -> bool:
    print(f"{'PASS' if ok else 'FAIL'}  {label:<64} {detail}", flush=True)
    return ok


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--env", required=True)
    p.add_argument("--target", action="append", required=True)
    p.add_argument("--source", action="append", default=[])
    p.add_argument("--stun-ports", default="3478,3479")
    p.add_argument("--relay-port", type=int, default=3480)
    p.add_argument("--range", default="3481-3496")
    p.add_argument("--rate-source", default="", help="a spare source address for the rate-limit check")
    a = p.parse_args()
    secret = env_secret(a.env)
    lo, hi = (int(x) for x in a.range.split("-"))
    sources = a.source or ["0.0.0.0"]
    ok = True
    for target in a.target:
        for src in sources:
            tag = f"{src}->{target}"
            for port in (int(x) for x in a.stun_ports.split(",")):
                s = sock(src)
                got = ask(s, binding_request(os.urandom(16), os.urandom(12)), (target, port))
                ok &= line(f"stun {tag}:{port} unissued token: no answer", got is None, f"answer={got!r}"[:60])
                got = ask(s, b"MCGS\x01\x01junk", (target, port))
                ok &= line(f"stun {tag}:{port} malformed: no answer", got is None, f"answer={got!r}"[:60])
                s.close()
            ctl = (target, a.relay_port)
            s = sock(src)
            bad = ticket(b"x" * 32, os.urandom(12), 0, int(time.time()) + 60, 1)
            got = ask(s, relay_bind(bad), ctl)
            ok &= line(f"relay {tag} bad-MAC ticket: no answer", got is None, f"answer={got!r}"[:60])
            got = ask(s, relay_bind(ticket(secret, os.urandom(12), 0, int(time.time()) - 5, 1)), ctl)
            ok &= line(f"relay {tag} expired ticket: refused(expired)", got is not None and parse_relay_answer(got).startswith("refused reason=2"), parse_relay_answer(got) if got else "no answer")
            got = ask(s, b"MCGR\x01\x01\x00\x05short", ctl)
            ok &= line(f"relay {tag} malformed bind: no answer", got is None, f"answer={got!r}"[:60])
            s.close()
            # a valid allocation: side 0 = A, side 1 = B; C is a third party
            alloc = os.urandom(12)
            exp = int(time.time()) + 120
            A, B, C = sock(src), sock(src), sock(src)
            ra = ask(A, relay_bind(ticket(secret, alloc, 0, exp, 1)), ctl)
            rb = ask(B, relay_bind(ticket(secret, alloc, 1, exp, 1)), ctl)
            pa = int(parse_relay_answer(ra).split("=")[1]) if ra and parse_relay_answer(ra).startswith("bound") else 0
            pb = int(parse_relay_answer(rb).split("=")[1]) if rb and parse_relay_answer(rb).startswith("bound") else 0
            ok &= line(f"relay {tag} valid tickets: both sides bound in {lo}-{hi}", lo <= pa <= hi and lo <= pb <= hi and pa != pb, f"side0={parse_relay_answer(ra) if ra else None} side1={parse_relay_answer(rb) if rb else None}")
            if pa and pb:
                got = ask(A, b"hello-from-A" * 4, (target, pa))  # A gets nothing back itself
                try:
                    data, frm = B.recvfrom(4096)
                except TimeoutError:
                    data, frm = None, None
                ok &= line(f"relay {tag} A->side0 forwarded to B from side1 port", data == b"hello-from-A" * 4 and frm is not None and frm[1] == pb, f"B got {len(data) if data else 0} bytes from port {frm[1] if frm else None}")
                B.sendto(b"reply-from-B", (target, pb))
                try:
                    data, frm = A.recvfrom(4096)
                except TimeoutError:
                    data, frm = None, None
                ok &= line(f"relay {tag} B->side1 forwarded to A from side0 port", data == b"reply-from-B" and frm is not None and frm[1] == pa, f"A got {len(data) if data else 0} bytes from port {frm[1] if frm else None}")
                C.sendto(b"third-party", (target, pa))
                try:
                    data = B.recvfrom(4096)[0]
                except TimeoutError:
                    data = None
                ok &= line(f"relay {tag} third party ->side0: dropped", data is None, f"B got {data!r}"[:60])
                A.sendto(b"x" * 3000, (target, pa))
                try:
                    data = B.recvfrom(4096)[0]
                except TimeoutError:
                    data = None
                ok &= line(f"relay {tag} 3000-byte packet: dropped (cap 2048)", data is None, f"B got {len(data) if data else 0} bytes")
            for x in (A, B, C):
                x.close()
            # max_mb=0: the allocation ends at its first packet
            alloc = os.urandom(12)
            A, B = sock(src), sock(src)
            ra = ask(A, relay_bind(ticket(secret, alloc, 0, exp, 0)), ctl)
            rb = ask(B, relay_bind(ticket(secret, alloc, 1, exp, 0)), ctl)
            if ra and rb and parse_relay_answer(ra).startswith("bound"):
                pa = int(parse_relay_answer(ra).split("=")[1])
                A.sendto(b"over-budget", (target, pa))
                try:
                    data = B.recvfrom(4096)[0]
                except TimeoutError:
                    data = None
                ok &= line(f"relay {tag} max_mb=0 allocation: nothing forwarded", data is None, f"B got {data!r}"[:60])
            for x in (A, B):
                x.close()
    if a.rate_source:
        s = sock(a.rate_source)
        for _ in range(16):  # all at once, then count the answers
            s.sendto(relay_bind(ticket(secret, os.urandom(12), 0, int(time.time()) - 5, 1)), (a.target[0], a.relay_port))
        n = 0
        while True:
            try:
                s.recvfrom(4096)
                n += 1
            except TimeoutError:
                break
        ok &= line(f"relay binds from {a.rate_source}: rate-limited (burst 10, 2/s)", 9 <= n <= 12, f"{n}/16 burst binds answered")
        s.close()
    print("ALL PASS" if ok else "SOME FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

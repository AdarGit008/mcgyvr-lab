"""Operator-only driver hub for the live validation (scratch, never in a repo).

Speaks the hub's v1 agent protocol on 127.0.0.1:PORT; each rig reaches it
through an ssh -R forward. It plays one pooled session: prepare both, tunnel
up both, start the worker, start the head, relay completions, stop both.
Writes every frame it sees (without relay bodies) to the evidence log.
"""

from __future__ import annotations

import base64
import json
import queue
import socket
import sys
import threading
import time
import uuid

sys.path.insert(0, sys.argv[1])  # the product checkout, for tests.rig_fake_hub
from tests.rig_fake_hub import CLOSE, PING, PONG, TEXT, Peer  # noqa: E402

PORT = int(sys.argv[2])
LOG = open(sys.argv[3], "a", buffering=1)
MODEL = sys.argv[4]
CTX = int(sys.argv[5])
SPLIT = [int(x) for x in sys.argv[6].split(",")]
REQUESTS = json.loads(open(sys.argv[7]).read())  # list of request bodies
HOLD = float(sys.argv[8]) if len(sys.argv) > 8 else 0.0  # seconds to keep up for probes
TUNNEL_NET = "10.211.7"


def log(what: str, **fields: object) -> None:
    LOG.write(json.dumps({"t": round(time.time(), 3), "what": what, **fields}) + "\n")
    print(what, json.dumps(fields)[:300], flush=True)


def frame(kind: str, body: dict, re: str | None = None) -> str:
    message = {"v": 1, "type": kind, "id": uuid.uuid4().hex, "body": body}
    if re:
        message["re"] = re
    return json.dumps(message)


class Rig:
    def __init__(self, peer: Peer) -> None:
        self.peer = peer
        self.inbox: queue.Queue[dict] = queue.Queue()
        self.hello: dict = {}
        self.lock = threading.Lock()

    def send(self, kind: str, body: dict, re: str | None = None) -> str:
        text = frame(kind, body, re)
        with self.lock:
            self.peer.send_text(text)
        if kind != "relay_data" and kind != "relay_credit":
            log("hub->" + self.name, type=kind, body=body)
        return json.loads(text)["id"]

    @property
    def name(self) -> str:
        return self.hello.get("machine_id", "?")[:12]

    def reader(self) -> None:
        while True:
            try:
                f = self.peer.recv_frame()
            except Exception as exc:
                log("closed", rig=self.name, why=repr(exc))
                return
            if f.opcode == PING:
                with self.lock:
                    self.peer.send_frame(PONG, f.payload)
                continue
            if f.opcode == CLOSE:
                log("close", rig=self.name)
                return
            if f.opcode != TEXT:
                continue
            m = json.loads(f.payload)
            if m["type"] == "heartbeat":
                self.send("ack", {}, m["id"])
                continue
            if m["type"] == "relay_data":
                log("rig->hub", rig=self.name, type="relay_data", seq=m["body"]["seq"],
                    bytes=len(base64.b64decode(m["body"]["data_b64"])))
            else:
                log("rig->hub", rig=self.name, type=m["type"], body=m.get("body"))
            self.inbox.put(m)

    def wait(self, pred, timeout: float) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                m = self.inbox.get(timeout=1)
            except queue.Empty:
                continue
            if pred(m):
                return m
        raise TimeoutError(f"{self.name}: nothing matched in {timeout}s")


rigs: list[Rig] = []
ready = threading.Event()


def serve() -> None:
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", PORT))
    listener.listen(4)
    while len(rigs) < 2:
        sock, _ = listener.accept()
        sock.settimeout(None)
        peer = Peer(sock)
        peer.handshake()
        hello = json.loads(peer.recv_text())
        rig = Rig(peer)
        rig.hello = hello["body"]
        log("hello", body=hello["body"])
        peer.send_text(frame("ack", {"rig_id": f"rig-{len(rigs)}", "heartbeat_interval_s": 15}, hello["id"]))
        threading.Thread(target=rig.reader, daemon=True).start()
        rigs.append(rig)
    ready.set()


threading.Thread(target=serve, daemon=True).start()
ready.wait()
head = next(r for r in rigs if len(r.hello.get("cards", [])) >= 2)
worker = next(r for r in rigs if r is not head)
sid = "live-" + uuid.uuid4().hex[:8]
log("roles", head=head.name, worker=worker.name, session=sid)

t0 = time.time()
for rig, role in ((head, "head"), (worker, "worker")):
    rig.send("session_prepare", {"session_id": sid, "role": role})
prepared = {}
for rig in (head, worker):
    m = rig.wait(lambda m: m["type"] in ("session_prepared", "session_status", "error"), 300)
    assert m["type"] == "session_prepared", m
    prepared[rig] = m["body"]
log("prepared", seconds=round(time.time() - t0, 1))


def peer_of(rig: Rig, me: int) -> dict:
    p = prepared[rig]
    return {
        "rig_id": "rig-" + str(rigs.index(rig)),
        "public_key": p["public_key"],
        "endpoints": p["endpoints"],
        "allowed_ips": [f"{TUNNEL_NET}.{me}/32"],
        "keepalive_s": 25,
    }


head.send("tunnel_up", {"session_id": sid, "address": f"{TUNNEL_NET}.1/24",
                        "listen_port": prepared[head]["listen_port"], "peers": [peer_of(worker, 2)]})
worker.send("tunnel_up", {"session_id": sid, "address": f"{TUNNEL_NET}.2/24",
                          "listen_port": prepared[worker]["listen_port"], "peers": [peer_of(head, 1)]})
for rig in (head, worker):
    m = rig.wait(lambda m: m["type"] in ("ack", "error"), 60)
    assert m["type"] == "ack", m
worker.send("worker_start", {"session_id": sid, "cards": [{"card_index": 0, "port": 50052}]})
m = worker.wait(lambda m: m["type"] == "session_status" and m["body"]["state"] in ("ready", "failed"), 300)
assert m["body"]["state"] == "ready", m
log("worker ready", seconds=round(time.time() - t0, 1))
t1 = time.time()
head.send("head_start", {"session_id": sid, "model": {"name": MODEL}, "ctx": CTX,
                         "devices": [{"kind": "local", "card_index": 0}, {"kind": "local", "card_index": 1},
                                     {"kind": "rpc", "host": f"{TUNNEL_NET}.2", "port": 50052}],
                         "tensor_split": SPLIT})
m = head.wait(lambda m: m["type"] == "session_status" and m["body"]["state"] in ("ready", "failed"), 1800)
assert m["body"]["state"] == "ready", m
log("head ready", load_seconds=round(time.time() - t1, 1))

for n, body in enumerate(REQUESTS):
    raw = json.dumps(body).encode()
    rid = f"req{n}-" + uuid.uuid4().hex[:6]
    started = time.time()
    head.send("relay_request", {"session_id": sid, "request_id": rid, "endpoint": "chat_completions",
                                "body_bytes": len(raw), "stream": bool(body.get("stream")),
                                "timeout_s": 600, "max_response_bytes": 8 << 20, "window": 8})
    for seq, i in enumerate(range(0, len(raw), 32768)):
        head.send("relay_data", {"request_id": rid, "seq": seq,
                                 "data_b64": base64.b64encode(raw[i:i + 32768]).decode()})
    chunks: list[bytes] = []
    while True:
        m = head.wait(lambda m: m["type"] in ("relay_response", "relay_data", "relay_end")
                      and m["body"].get("request_id") == rid, 900)
        if m["type"] == "relay_data":
            chunks.append(base64.b64decode(m["body"]["data_b64"]))
            head.send("relay_credit", {"request_id": rid, "chunks": 1})
        elif m["type"] == "relay_end":
            break
    text = b"".join(chunks).decode("utf-8", "replace")
    result: dict = {"outcome": m["body"], "wall_s": round(time.time() - started, 2), "frames": len(chunks)}
    if not body.get("stream"):
        answer = json.loads(text)
        result["timings"] = answer.get("timings")
        result["usage"] = answer.get("usage")
        result["reply_head"] = answer["choices"][0]["message"]["content"][:120]
    else:
        result["sse_events"] = text.count("data: ")
        result["tail"] = text[-200:]
    log("relay", n=n, **result)

if HOLD:
    log("holding for probes", seconds=HOLD)
    open(sys.argv[3] + ".hold", "w").write(sid)
    deadline = time.time() + HOLD
    while time.time() < deadline and not __import__("os").path.exists(sys.argv[3] + ".release"):
        time.sleep(1)

for rig in (head, worker):
    rig.send("session_stop", {"session_id": sid, "reason": "done"})
for rig in (head, worker):
    m = rig.wait(lambda m: m["type"] == "session_status" and m["body"]["state"] == "stopped", 300)
log("stopped", seconds=round(time.time() - t0, 1))
time.sleep(2)

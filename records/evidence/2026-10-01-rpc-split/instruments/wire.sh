#!/usr/bin/env bash
# records/evidence/2026-10-01-rpc-split/instruments/wire.sh — what crosses the wire between the
# head and the worker, run by hand from the operator's machine (the campaign is tools/runs/campaigns/rpc-split). NOT a door
# step: it needs both rigs at once, and the door reaches exactly one host.
# Everything it starts it stops; the worker (rpc-server) is the operator's.
#
#   wire.sh OUT_DIR PHASE
#
#   lan    head --rpc through rpcwire.py on the head, relay -> worker LAN ip.
#          Load bytes, then per-request rows: short and long prompts at 1 and
#          129 output tokens (the differences give per-token and
#          per-prompt-token cost), then the relay's added RTT / rate arms.
#   reload two loads in a row through the relay at RTT 0 against a worker
#          started with -c: bytes and wall of each, nothing else.
#   direct head --rpc straight at RPC_ENDPOINT (no relay), short and long
#          prompts; interface counters only. Used for the tailnet path with
#          RPC_ENDPOINT set to the worker's tailnet address.
#
# Model, window and flags are the driver's (mgpu_sweep.py) for layout=layer.

set -euo pipefail
OUT=$1
PHASE=$2
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
HEAD=srv1
IFACE=${IFACE:-enp4s0}
IMG=llamacpp:b10644-L3-rpc
MODEL=${MODEL:-/models/dense/Qwen2.5-Coder-32B-Instruct-Q4_K_M.gguf}
CTX=${CTX:-4096}
RPC_ENDPOINT=${RPC_ENDPOINT:-192.168.1.167:50052}
RELAY=127.0.0.1:50053
PORT=8091
W=/home/adaramir/stage0-rpc/wire
NAME=wire-head
x() { ssh -o BatchMode=yes "$HEAD" "$@"; }

stamp() {
    x "echo '## $1' \$(date -Is); nvidia-smi --query-gpu=index,name,pci.bus_id,memory.used,memory.free,driver_version --format=csv,noheader; echo apps:; nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; docker image inspect $IMG --format 'img={{.Id}}'; grep MemAvailable /proc/meminfo; for k in rx_bytes tx_bytes rx_packets tx_packets; do echo -n \"if_\$k=\$(cat /sys/class/net/$IFACE/statistics/\$k) \"; done; echo"
}

relay_up() {
    x "mkdir -p $W" </dev/null
    scp -q -o BatchMode=yes "$HERE/rpcwire.py" "$HEAD:$W/rpcwire.py"
    x "echo '{\"rtt_ms\": 0, \"mbit\": 0}' > $W/ctl.json; rm -f $W/stats.json; cd $W; nohup python3 $W/rpcwire.py $RELAY $RPC_ENDPOINT $W/ctl.json $W/stats.json > $W/relay.log 2>&1 < /dev/null & echo \$! > $W/relay.pid; sleep 1; cat $W/stats.json"
}

relay_down() { x "kill \$(cat $W/relay.pid) 2>/dev/null; rm -f $W/relay.pid" || true; }

head_up() {  # $1 = rpc endpoint the head dials
    x "nvidia-smi --query-compute-apps=pid --format=csv,noheader | grep -q . && { echo 'REFUSED: a compute app holds a card'; exit 1; }; docker ps -q | grep -q . && { echo 'REFUSED: a container is up'; exit 1; }; t0=\$(date +%s.%N); docker run -d --name $NAME --gpus all --network host -e CUDA_DEVICE_ORDER=PCI_BUS_ID -v /home/adaramir/models:/models:ro $IMG -m $MODEL -ngl 99 -sm layer -np 1 -c $CTX -fa on -ctk q8_0 -ctv q8_0 --no-warmup -lv 4 --host 127.0.0.1 --port $PORT --rpc $1 >/dev/null; for i in \$(seq 1 450); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; docker ps -q -f name=$NAME | grep -q . || break; sleep 1; done; curl -sf http://127.0.0.1:$PORT/health >/dev/null || { echo 'REFUSED: head never healthy'; docker logs $NAME 2>&1 | tail -5; exit 1; }; echo load_wall_s=\$(awk -v a=\$t0 -v b=\$(date +%s.%N) 'BEGIN{printf \"%.1f\", b-a}')"
}

head_down() {  # $1 = log file name
    x "docker logs $NAME" >"$OUT/$1" 2>&1 || true
    x "docker rm -f $NAME >/dev/null 2>&1 || true"
}

probe() { x "python3 - $PORT $W/stats.json $W/ctl.json $IFACE $*" <"$HERE/wire_probe.py"; }

trap 'head_down wire-$PHASE-head.trap.log; relay_down' ERR INT

case $PHASE in
lan)
    stamp before >"$OUT/wire-lan.txt"
    relay_up >>"$OUT/wire-lan.txt"
    head_up "$RELAY" >>"$OUT/wire-lan.txt"
    x "cat $W/stats.json" | sed 's/^/load_stats=/' >>"$OUT/wire-lan.txt"
    stamp loaded >>"$OUT/wire-lan.txt"
    probe warm:short:0:0:16 \
        s1:short:0:0:1 s129:short:0:0:129 l1:long:0:0:1 l129:long:0:0:129 \
        s1b:short:0:0:1 s129b:short:0:0:129 \
        r5:short:5:0:65 r20:short:20:0:65 r80:short:80:0:33 r150:short:150:0:33 \
        lr20:long:20:0:1 lr80:long:80:0:1 lr150:long:150:0:1 \
        b20r20:short:20:20:33 b20r80:short:80:20:33 lb20r20:long:20:20:1 lb20r80:long:80:20:1 \
        r0end:short:0:0:65 >"$OUT/wire-lan.jsonl"
    head_down wire-lan-head.log
    relay_down
    stamp after >>"$OUT/wire-lan.txt"
    ;;
reload)
    stamp before >"$OUT/wire-reload.txt"
    relay_up >>"$OUT/wire-reload.txt"
    for n in 1 2; do
        x "cat $W/stats.json" | sed "s/^/pre_load$n=/" >>"$OUT/wire-reload.txt"
        head_up "$RELAY" | sed "s/^/load$n /" >>"$OUT/wire-reload.txt"
        x "cat $W/stats.json" | sed "s/^/post_load$n=/" >>"$OUT/wire-reload.txt"
        probe "warm$n:short:0:0:16" >>"$OUT/wire-reload.jsonl"
        head_down "wire-reload-head-$n.log"
    done
    relay_down
    stamp after >>"$OUT/wire-reload.txt"
    ;;
direct)
    stamp before >"$OUT/wire-direct.txt"
    head_up "$RPC_ENDPOINT" >>"$OUT/wire-direct.txt"
    stamp loaded >>"$OUT/wire-direct.txt"
    # no relay: a stats file that never moves, so only the interface deltas count
    x "mkdir -p $W && echo '{\"c2s_bytes\":0,\"s2c_bytes\":0,\"cmd_n\":{},\"cmd_bytes\":{}}' > $W/stats.json && echo '{}' > $W/ctl.json"
    probe warm:short:0:0:16 s1:short:0:0:1 s129:short:0:0:129 l1:long:0:0:1 s129b:short:0:0:129 >"$OUT/wire-direct.jsonl"
    head_down wire-direct-head.log
    stamp after >>"$OUT/wire-direct.txt"
    ;;
*) echo "unknown phase $PHASE" >&2; exit 2 ;;
esac

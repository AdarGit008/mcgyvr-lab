# shellcheck shell=bash
# tools/runs/campaigns/rpc-split/_rpc.sh — what every step of rpc-split
# shares, sourced after tools/runs/_common.sh. Executes nothing.
#
# The head is the door's host (srv1, two cards). The worker is a
# ggml-rpc-server the operator starts by hand on RPC_WORKER, bound to its LAN
# address only (the server has no authentication), from the same image:
#
#   docker run -d --name rpcw --gpus all --network host \
#     --entrypoint /app/ggml-rpc-server llamacpp:b10644-L3-rpc \
#     -H <worker LAN ip> -p 50052 [-d CUDA0 | -d CUDA0,CPU] [-c]
#
# The door neither sees nor stops it, and its ssh shim refuses any host but
# the one the run was opened for, so the worker's card and the rpc-server's
# argv are read by hand from outside the door, before and after each step, into
# worker-<step>.txt beside the TSV. The operator removes it.
#
#   rpc_serve ARTIFACT CELL...   mgpu_serve on RPC_IMG instead of hosts.json's
#                                image, refused unless the worker answers

# shellcheck source=../srv1-multi-gpu/_mgpu.sh disable=SC1091
. "$RUN_ROOT/tools/runs/campaigns/srv1-multi-gpu/_mgpu.sh"

RPC_IMG=llamacpp:b10644-L3-rpc
RPC_WORKER=srv2
RPC_ENDPOINT=192.168.1.167:50052

say() { printf 'rpc-split: %s\n' "$*" >&2; }

rpc_serve() {
    local artifact=$1 digest
    shift
    mgpu_preamble "$artifact"
    "$SSH" "$RUN_HOST" "timeout 3 bash -c '</dev/tcp/${RPC_ENDPOINT%:*}/${RPC_ENDPOINT#*:}'" </dev/null ||
        { _fail "REFUSED — no rpc-server answers at $RPC_ENDPOINT from $RUN_HOST" || true; exit 2; }
    digest=$(image_digest "$RPC_IMG") || { _fail "$RPC_IMG resolves to no digest on $RUN_HOST" || true; exit 1; }
    export LCP_IMG="$digest"
    trap '"$DOCKER" rm -f "$RUN_ID-mgpu-a" "$RUN_ID-mgpu-b" >/dev/null 2>&1 || true' EXIT
    open_tsv workload_stamp tools/runs/workload.py
    emit stamp NOTE "image=$RPC_IMG" "rpc_endpoint=$RPC_ENDPOINT" "worker=$RPC_WORKER"
    say "lcp: $# cells"
    emit rig_stamp
    emit _py tools/runs/drivers/mgpu_sweep.py lcp "$@"
    close_tsv
    say "wrote $OUT"
}

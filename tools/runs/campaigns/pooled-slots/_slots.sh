# shellcheck shell=bash
# tools/runs/campaigns/pooled-slots/_slots.sh — what every step of
# pooled-slots shares, sourced after tools/runs/_common.sh. Executes nothing.
#
# Issue #46 step 1 (records/plans/hub-batching-2026-10-02.md §4). The
# instrument is rpc-split's, as it stands: the head is the door's host (srv1,
# two cards), the worker a ggml-rpc-server on srv2 that the operator starts by
# hand and removes after (rpc-split/_rpc.sh), both on llamacpp:b10644-L3-rpc.
# What is added here is one driver invocation per cell: the prompt draw is a
# per-process counter, so two cells in one argv do not draw alike
# (okf/must-read/reading-results.md), and the arms are interleaved cell by
# cell, never run in blocks (okf/must-read/touching-engine.md).
#
# Two configs, one checkpoint (Qwen2.5-Coder-32B-Instruct Q5_K_M, the pooled
# head's and rpc-split's q5 pair's), one image, -sm layer, -fa on, q8_0 KV:
#
#   H  head-only: srv1's two cards at llama.cpp's default split
#   S  split: the two cards plus the worker as RPC0, placed as today's pooled
#      head is (-dev CUDA0,CUDA1,RPC0 -ts 27,26,12, lab PR #42
#      records/evidence/2026-10-02-pooled-e2e/e2e/head-args-3.txt), so the
#      worker holds layers 53..63 and the output layer
#
# Every cell runs levels 1,2,4 and pins its slots with @np; the per-slot window
# is W = 2048 unless a cell says otherwise, so -c = slots x 2048. @headroom
# skips the driver's fit prediction, which counts the head's cards only (as
# rpc-split's q5 cells did): the engine's refusal decides.
#
#   slots_serve ARTIFACT CELL...   rpc_serve, but one driver invocation per cell
#   slots_round R                  the cells of one round, tags suffixed -R

# shellcheck source=../rpc-split/_rpc.sh disable=SC1091
. "$RUN_ROOT/tools/runs/campaigns/rpc-split/_rpc.sh"

say() { printf 'pooled-slots: %s\n' "$*" >&2; }

Q5=/models/dense/Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf
W=2048
LEVELS=1,2,4
F="@headroom=-30000"
#: the split config, and the same split with the output layer on CUDA1
#: (RPC0 still 11 layers, CUDA0 27, CUDA1 26 + output): desk read cell 6
S="--rpc+$RPC_ENDPOINT+-dev+CUDA0,CUDA1,RPC0+-ts+27,26,12"
S_OUT1="--rpc+$RPC_ENDPOINT+-dev+RPC0,CUDA0,CUDA1+-ts+11,27,27"

slots_serve() {
    local artifact=$1 digest cell
    shift
    mgpu_preamble "$artifact"
    "$SSH" "$RUN_HOST" "timeout 3 bash -c '</dev/tcp/${RPC_ENDPOINT%:*}/${RPC_ENDPOINT#*:}'" </dev/null ||
        { _fail "REFUSED — no rpc-server answers at $RPC_ENDPOINT from $RUN_HOST" || true; exit 2; }
    digest=$(image_digest "$RPC_IMG") || { _fail "$RPC_IMG resolves to no digest on $RUN_HOST" || true; exit 1; }
    export LCP_IMG="$digest"
    trap '"$DOCKER" rm -f "$RUN_ID-mgpu-a" "$RUN_ID-mgpu-b" >/dev/null 2>&1 || true' EXIT
    open_tsv workload_stamp tools/runs/workload.py
    emit stamp NOTE "image=$RPC_IMG" "rpc_endpoint=$RPC_ENDPOINT" "worker=$RPC_WORKER" "cells=$#" "one_driver_per_cell=yes"
    emit rig_stamp
    for cell in "$@"; do
        say "lcp: ${cell%%:*}"
        emit _py tools/runs/drivers/mgpu_sweep.py lcp "$cell"
    done
    close_tsv
    say "wrote $OUT"
}

# The order the plan gives (§4): the arms H1 S1 H2 S2 H4 S4, the nulls, then
# the desk read's cells 1-7.
slots_round() {
    local r=$1
    local m="$Q5:layer:built"
    printf '%s\n' \
        "H1-$r:$m:$W:$LEVELS:$F+@np=1" \
        "S1-$r:$m:$W:$LEVELS:$S+$F+@np=1" \
        "H2-$r:$m:$W:$LEVELS:$F+@np=2" \
        "S2-$r:$m:$W:$LEVELS:$S+$F+@np=2" \
        "H4-$r:$m:$W:$LEVELS:$F+@np=4" \
        "S4-$r:$m:$W:$LEVELS:$S+$F+@np=4" \
        "S1N-$r:$m:$W:$LEVELS:$S+$F+@np=1" \
        "S4N-$r:$m:$W:$LEVELS:$S+$F+@np=4" \
        "H1N-$r:$m:$W:$LEVELS:$F+@np=1" \
        "H4N-$r:$m:$W:$LEVELS:$F+@np=4" \
        "D1S2-$r:$m:6144:$LEVELS:$S+$F+@np=2" \
        "D1S4-$r:$m:3072:$LEVELS:$S+$F+@np=4" \
        "D2KVU-$r:$m:3072:$LEVELS:$S+-kvu+$F+@np=4" \
        "D2FILL-$r:$m:3072:$LEVELS:$S+-kvu+-c+3072+$F+@np=4" \
        "D3HELD-$r:$m:$W:$LEVELS:$S+$F+@np=1+@stagger=0.5" \
        "D4GAP-$r:$m:$W:$LEVELS:$S+$F+@np=4+@id_slot=0,2,1,3" \
        "D4SEQ-$r:$m:$W:$LEVELS:$S+$F+@np=4+@id_slot=0,1,2,3" \
        "D5STAG-$r:$m:$W:$LEVELS:$S+$F+@np=4+@stagger=3" \
        "D6OUT1-$r:$m:$W:$LEVELS:$S_OUT1+$F+@np=4" \
        "D7NOCACHE-$r:$m:$W:$LEVELS:$S+--cache-ram+0+$F+@np=2"
}

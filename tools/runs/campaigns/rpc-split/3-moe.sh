#!/usr/bin/env bash
# tools/runs/campaigns/rpc-split/3-moe.sh — step 3: an 80B MoE larger than
# all three cards together, experts of the first N blocks in host RAM
# (--n-cpu-moe N), the rest across the cards. -dev puts the worker's card
# LAST, so it takes the top blocks, whose experts are on the card; -ts gives
# each card whole blocks (n_layer + output = 49 units), derived from the
# tensor table's per-block expert bytes against each card's free memory.
# The w-cells hold the same N blocks' experts in the WORKER's RAM (RPC1, its
# CPU device) instead of the head's: -ot names them before --n-cpu-moe.
#
# RUN_ARTIFACTS: moe.tsv
#
# worker: ggml-rpc-server -d CUDA0,CPU on srv2 (see _rpc.sh)
# python -m mcgyvr.serving.run --host srv1 --campaign rpc-split \
#   --step tools/runs/campaigns/rpc-split/3-moe.sh \
#   --model /models/moe/Qwen3-Next-80B-A3B-Instruct-Q3_K_M.gguf --ctx-per-slot 16384

[ -n "${RUN_ID:-}" ] || { echo "3-moe.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_rpc.sh disable=SC1091
. "$HERE/_rpc.sh"

X=/models/moe/Qwen3-Next-80B-A3B-Instruct-Q3_K_M.gguf
R="--rpc+$RPC_ENDPOINT+-dev+CUDA0,CUDA1,RPC0"
W="--rpc+$RPC_ENDPOINT+-dev+CUDA0,CUDA1,RPC0,RPC1"
WB="RPC1[$RPC_ENDPOINT]"
cells=(
    "n80-local-cm22:$X:layer:built:16384:1:--n-cpu-moe+22+-ts+35,14"
    "n80-local-cm21:$X:layer:built:16384:1:--n-cpu-moe+21+-ts+35,14"
    "n80-local-cm20:$X:layer:built:16384:1:--n-cpu-moe+20+-ts+34,15"
    "n80-rpc-cm18:$X:layer:built:16384:1:$R+--n-cpu-moe+18+-ts+31,13,5"
    "n80-rpc-cm16:$X:layer:built:16384:1:$R+--n-cpu-moe+16+-ts+30,13,6"
    "n80-rpc-cm14:$X:layer:built:16384:1:$R+--n-cpu-moe+14+-ts+28,14,7"
    "n80-rpc-cm13:$X:layer:built:16384:1:$R+--n-cpu-moe+13+-ts+28,14,7"
    "n80-rpcw-cm16:$X:layer:built:16384:1:$W+-ts+30,13,6,0+-ot+'blk\\.([0-9]|1[0-5])\\.ffn_.*_exps\\.=$WB'+--n-cpu-moe+16"
)
rpc_serve moe.tsv "${cells[@]}"

#!/usr/bin/env bash
# tools/runs/campaigns/rpc-split/1-xcard.sh — step 1: a dense checkpoint
# whose weights plus KV at a working window do not fit the head's two cards
# and do fit with the worker's card added. Both arms forced past the driver's
# fit prediction (@headroom), which counts the head's cards only: the
# head-only refusal is the measurement.
#
# RUN_ARTIFACTS: xcard.tsv
#
# worker: ggml-rpc-server -d CUDA0 on srv2 (see _rpc.sh)
# python -m mcgyvr.serving.run --host srv1 --campaign rpc-split \
#   --step tools/runs/campaigns/rpc-split/1-xcard.sh \
#   --model /models/dense/Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf --ctx-per-slot 4096

[ -n "${RUN_ID:-}" ] || { echo "1-xcard.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_rpc.sh disable=SC1091
. "$HERE/_rpc.sh"

Q5=/models/dense/Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf
R="--rpc+$RPC_ENDPOINT"
F="@headroom=-30000"
cells=(
    "q5-local-4096:$Q5:layer:built:4096:1:$F"
    "q5-local-16384:$Q5:layer:built:16384:1:$F+@prefill=27300"
    "q5-rpc-16384:$Q5:layer:built:16384:1:$R+$F+@prefill=27300"
    "q5-rpc-32768:$Q5:layer:built:32768:1:$R+$F+@prefill=54600"
)
rpc_serve xcard.tsv "${cells[@]}"

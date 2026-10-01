#!/usr/bin/env bash
# tools/runs/campaigns/rpc-split/9-pair-q5-rpc.sh — step 9: one cell alone in its
# driver invocation, so its prompt draw matches its pair's (steps 6/7 and
# 8/9 are head-only against head+worker at one window; decode and prefill at
# equal window and equal draw are the cost of the worker's card).
#
# RUN_ARTIFACTS: pair-q5-rpc.tsv
#
# worker: ggml-rpc-server -d CUDA0 on srv2 (see _rpc.sh)
# python -m mcgyvr.serving.run --host srv1 --campaign rpc-split \
#   --step tools/runs/campaigns/rpc-split/9-pair-q5-rpc.sh --model /models/dense/Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf --ctx-per-slot 4096

[ -n "${RUN_ID:-}" ] || { echo "9-pair-q5-rpc.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_rpc.sh disable=SC1091
. "$HERE/_rpc.sh"

rpc_serve pair-q5-rpc.tsv "q5-rpc-8192:/models/dense/Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf:layer:built:8192:1:--rpc+$RPC_ENDPOINT+@prefill=2800+@knob+@headroom=-30000"

#!/usr/bin/env bash
# tools/runs/campaigns/rpc-split/7-pair-a3b-rpc.sh — step 7: one cell alone in its
# driver invocation, so its prompt draw matches its pair's (steps 6/7 and
# 8/9 are head-only against head+worker at one window; decode and prefill at
# equal window and equal draw are the cost of the worker's card).
#
# RUN_ARTIFACTS: pair-a3b-rpc.tsv
#
# worker: ggml-rpc-server -d CUDA0 on srv2 (see _rpc.sh)
# python -m mcgyvr.serving.run --host srv1 --campaign rpc-split \
#   --step tools/runs/campaigns/rpc-split/7-pair-a3b-rpc.sh --model /models/moe/qwen3-coder-30b.gguf --ctx-per-slot 4096

[ -n "${RUN_ID:-}" ] || { echo "7-pair-a3b-rpc.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_rpc.sh disable=SC1091
. "$HERE/_rpc.sh"

rpc_serve pair-a3b-rpc.tsv "a3b-rpc-65536:/models/moe/qwen3-coder-30b.gguf:layer:built:65536:1:--rpc+$RPC_ENDPOINT+@prefill=2800+@knob"

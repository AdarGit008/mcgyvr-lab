#!/usr/bin/env bash
# tools/runs/campaigns/rpc-split/6-pair-a3b-local.sh — step 6: one cell alone in its
# driver invocation, so its prompt draw matches its pair's (steps 6/7 and
# 8/9 are head-only against head+worker at one window; decode and prefill at
# equal window and equal draw are the cost of the worker's card).
#
# RUN_ARTIFACTS: pair-a3b-local.tsv
#
# worker: ggml-rpc-server -d CUDA0 on srv2 (see _rpc.sh)
# python -m mcgyvr.serving.run --host srv1 --campaign rpc-split \
#   --step tools/runs/campaigns/rpc-split/6-pair-a3b-local.sh --model /models/moe/qwen3-coder-30b.gguf --ctx-per-slot 4096

[ -n "${RUN_ID:-}" ] || { echo "6-pair-a3b-local.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_rpc.sh disable=SC1091
. "$HERE/_rpc.sh"

rpc_serve pair-a3b-local.tsv "a3b-local-65536:/models/moe/qwen3-coder-30b.gguf:layer:built:65536:1:@prefill=2800+@knob"

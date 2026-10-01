#!/usr/bin/env bash
# tools/runs/campaigns/rpc-split/4-xcard-local.sh — step 4: the head-only ceiling of step 1's dense checkpoint, bracketing
# between the 4k that loaded and the 16k that was refused on the head's two
# cards alone, forced past the fit prediction (@headroom). The worker is only
# checked for, not used.
#
# RUN_ARTIFACTS: xcard-local.tsv
#
# worker: ggml-rpc-server -d CUDA0 on srv2 (see _rpc.sh)
# python -m mcgyvr.serving.run --host srv1 --campaign rpc-split \
#   --step tools/runs/campaigns/rpc-split/4-xcard-local.sh \
#   --model /models/dense/Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf --ctx-per-slot 4096

[ -n "${RUN_ID:-}" ] || { echo "4-xcard-local.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_rpc.sh disable=SC1091
. "$HERE/_rpc.sh"

Q5=/models/dense/Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf
F="@headroom=-30000"
cells=(
    "q5-local-8192:$Q5:layer:built:8192:1:$F+@prefill=13600"
    "q5-local-12288:$Q5:layer:built:12288:1:$F+@prefill=20400"
)
rpc_serve xcard-local.tsv "${cells[@]}"

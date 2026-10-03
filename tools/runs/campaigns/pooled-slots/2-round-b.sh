#!/usr/bin/env bash
# tools/runs/campaigns/pooled-slots/2-round-b.sh — step 2: round b of three,
# the same cells in the same order as 1-round-a.sh (_slots.sh slots_round).
#
# RUN_ARTIFACTS: round-b.tsv
#
# worker: ggml-rpc-server -d CUDA0 on srv2 (see rpc-split/_rpc.sh)
# python -m mcgyvr.serving.run --host srv1 --campaign pooled-slots \
#   --step tools/runs/campaigns/pooled-slots/2-round-b.sh \
#   --model /models/dense/Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf --ctx-per-slot 2048

[ -n "${RUN_ID:-}" ] || { echo "2-round-b.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_slots.sh disable=SC1091
. "$HERE/_slots.sh"

mapfile -t cells < <(slots_round b)
slots_serve round-b.tsv "${cells[@]}"

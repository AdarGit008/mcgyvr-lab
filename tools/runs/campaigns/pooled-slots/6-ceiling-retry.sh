#!/usr/bin/env bash
# tools/runs/campaigns/pooled-slots/6-ceiling-retry.sh — step 6: step 4's
# refusals retried, and the rung between. Step 4 loaded a total of 40960 at
# -np 1, 2 and 4 and was refused at 49152 at all three, once each: the
# engine's words ("failed to create context") are not the driver's memory
# words, so the driver did not retry them, and a refusal is retried three
# times before it is believed (okf/must-read/touching-rigs.md). Here 49152 is
# tried twice more at each -np, and 45056 once at each.
#
# RUN_ARTIFACTS: ceiling-retry.tsv
#
# worker: ggml-rpc-server -d CUDA0 on srv2 (see rpc-split/_rpc.sh)
# python -m mcgyvr.serving.run --host srv1 --campaign pooled-slots \
#   --step tools/runs/campaigns/pooled-slots/6-ceiling-retry.sh \
#   --model /models/dense/Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf --ctx-per-slot 2048

[ -n "${RUN_ID:-}" ] || { echo "6-ceiling-retry.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_slots.sh disable=SC1091
. "$HERE/_slots.sh"

cells=()
for try in t2 t3; do
    for np in 1 2 4; do
        cells+=("C$np-49152$try:$Q5:layer:built:$((49152 / np)):1:$S+$F+@np=$np")
    done
done
for np in 1 2 4; do
    cells+=("C$np-45056t1:$Q5:layer:built:$((45056 / np)):1:$S+$F+@np=$np")
done
slots_serve ceiling-retry.tsv "${cells[@]}"

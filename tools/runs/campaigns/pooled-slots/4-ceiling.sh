#!/usr/bin/env bash
# tools/runs/campaigns/pooled-slots/4-ceiling.sh — step 4: the per-slot
# context ceiling of the split config at -np 1, 2 and 4, a ladder up to the
# first refusal, which is the measurement; the driver retries a refusal whose
# words are about memory three times before filing it. One request (level 1)
# reads each load back; the CONFIG row's per-device KV and compute buffers are
# read against slots x ctx. The rungs are equal totals (-c = slots x ctx) at
# the three slot counts; CEILING_TOTALS overrides them for a refining run.
#
# RUN_ARTIFACTS: ceiling.tsv
#
# worker: ggml-rpc-server -d CUDA0 on srv2 (see rpc-split/_rpc.sh)
# python -m mcgyvr.serving.run --host srv1 --campaign pooled-slots \
#   --step tools/runs/campaigns/pooled-slots/4-ceiling.sh \
#   --model /models/dense/Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf --ctx-per-slot 2048

[ -n "${RUN_ID:-}" ] || { echo "4-ceiling.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_slots.sh disable=SC1091
. "$HERE/_slots.sh"

cells=()
for total in ${CEILING_TOTALS:-32768 40960 49152}; do
    for np in 1 2 4; do
        cells+=("C$np-$total:$Q5:layer:built:$((total / np)):1:$S+$F+@np=$np")
    done
done
slots_serve ceiling.tsv "${cells[@]}"

#!/usr/bin/env bash
# tools/runs/campaigns/pooled-slots/5-fill.sh — step 5: desk read cell 2's
# fill, again, with a pool the workload can fill. The rounds' D2FILL cell
# (-kvu, four slots sharing one pool of -c 3072) never filled: the four
# concurrent workload requests of level 4 did not hold 3072 cells at once, so
# every request answered and the failure mode (§Q1: a full shared pool fails
# every running request together) was not reached. Here the shared pool is
# -c 2048: level 4's four prompts alone are ~2500 tokens, while every single
# request, and level 2's pair, fits. Three invocations, each its own driver
# run: a refusal is retried three times before it is believed.
#
# RUN_ARTIFACTS: fill.tsv
#
# worker: ggml-rpc-server -d CUDA0 on srv2 (see rpc-split/_rpc.sh)
# python -m mcgyvr.serving.run --host srv1 --campaign pooled-slots \
#   --step tools/runs/campaigns/pooled-slots/5-fill.sh \
#   --model /models/dense/Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf --ctx-per-slot 2048

[ -n "${RUN_ID:-}" ] || { echo "5-fill.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_slots.sh disable=SC1091
. "$HERE/_slots.sh"

cells=()
for try in 1 2 3; do
    cells+=("D2FILL2048-t$try:$Q5:layer:built:2048:$LEVELS:$S+-kvu+-c+2048+$F+@np=4")
done
slots_serve fill.tsv "${cells[@]}"

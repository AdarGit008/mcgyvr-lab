#!/usr/bin/env bash
# tools/runs/campaigns/rpc-split/5-ctx-fine.sh — step 5: step 2's ceilings
# refined. Head-only between the 64k that loaded and the 96k that was refused;
# head+worker at the default split between 128k and 160k, and with -ts moving
# layers off the worker's card — the default split is proportional to free
# memory and refuses on the worker's card while ~1.5 GiB stays free on each
# head card. The -ts values are layers per device (RPC0, CUDA0, CUDA1; 48
# blocks + output), from the tensor table's per-block bytes plus q8_0 KV per
# block at the window against each card's free memory less its compute buffer.
#
# RUN_ARTIFACTS: ctx-fine.tsv
#
# worker: ggml-rpc-server -d CUDA0 on srv2 (see _rpc.sh)
# python -m mcgyvr.serving.run --host srv1 --campaign rpc-split \
#   --step tools/runs/campaigns/rpc-split/5-ctx-fine.sh \
#   --model /models/moe/qwen3-coder-30b.gguf --ctx-per-slot 4096

[ -n "${RUN_ID:-}" ] || { echo "5-ctx-fine.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_rpc.sh disable=SC1091
. "$HERE/_rpc.sh"

M=/models/moe/qwen3-coder-30b.gguf
R="--rpc+$RPC_ENDPOINT"
P="@prefill=54600"
cells=()
for ctx in 73728 81920 90112; do
    cells+=("a3b-local-$ctx:$M:layer:built:$ctx:1:$P")
done
cells+=("a3b-rpc-147456:$M:layer:built:147456:1:$R+$P")
for ctx in 163840 180224 196608; do
    cells+=("a3b-rpcts-$ctx:$M:layer:built:$ctx:1:$R+-ts+9,20,20+$P")
done
rpc_serve ctx-fine.tsv "${cells[@]}"

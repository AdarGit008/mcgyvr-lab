#!/usr/bin/env bash
# tools/runs/campaigns/rpc-split/2-ctx.sh — step 2: the context ceiling of a
# checkpoint that fits the head alone, on the head's two cards and with the
# worker's card added, one stream (-np 1, so -c is the window). Every cell
# sends the same PREFILL size, so decode at equal window is comparable across
# the two arms. The last rung that loads is the ceiling; the first refusal is
# the measurement.
#
# RUN_ARTIFACTS: ctx.tsv
#
# worker: ggml-rpc-server -d CUDA0 on srv2 (see _rpc.sh)
# python -m mcgyvr.serving.run --host srv1 --campaign rpc-split \
#   --step tools/runs/campaigns/rpc-split/2-ctx.sh \
#   --model /models/moe/qwen3-coder-30b.gguf --ctx-per-slot 4096

[ -n "${RUN_ID:-}" ] || { echo "2-ctx.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

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
for ctx in ${LADDER_LOCAL:-65536 98304 114688 131072}; do
    cells+=("a3b-local-$ctx:$M:layer:built:$ctx:1:$P")
done
for ctx in ${LADDER_RPC:-65536 131072 163840 196608 229376 262144}; do
    cells+=("a3b-rpc-$ctx:$M:layer:built:$ctx:1:$R+$P")
done
rpc_serve ctx.tsv "${cells[@]}"

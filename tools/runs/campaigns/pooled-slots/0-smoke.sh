#!/usr/bin/env bash
# tools/runs/campaigns/pooled-slots/0-smoke.sh — step 0: the arms' widest
# launch loads on both configs at the arms' window before any round spends
# rig time on it (four slots x W = 2048, -c 8192; rpc-split filed the
# head-only config loaded at -c 8192 and refused at 12288 with one slot),
# and the driver's new rows read back: REQ rows, slots= from the server's
# log, n_seq_max= and kv_unified= in CONFIG, id_slot honoured.
#
# RUN_ARTIFACTS: smoke.tsv
#
# worker: ggml-rpc-server -d CUDA0 on srv2 (see rpc-split/_rpc.sh)
# python -m mcgyvr.serving.run --host srv1 --campaign pooled-slots \
#   --step tools/runs/campaigns/pooled-slots/0-smoke.sh \
#   --model /models/dense/Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf --ctx-per-slot 2048

[ -n "${RUN_ID:-}" ] || { echo "0-smoke.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_slots.sh disable=SC1091
. "$HERE/_slots.sh"

slots_serve smoke.tsv \
    "H4-smoke:$Q5:layer:built:$W:1:$F+@np=4" \
    "S4-smoke:$Q5:layer:built:$W:1,2:$S+$F+@np=4+@id_slot=0,2,1,3"

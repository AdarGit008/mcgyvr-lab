#!/usr/bin/env bash
# tools/runs/campaigns/pooled-slots/1-round-a.sh — step 1: round a of three.
# One round is every arm (H1 S1 H2 S2 H4 S4), the null replicates the tie bar
# and the round-trip reading are priced from (S1N S4N H1N H4N), and the desk
# read's cells 1-7, in that order, one driver invocation per cell
# (_slots.sh slots_round). The rounds are the plan's "then again": the same
# order three times, so every arm and every null has three invocations.
#
# RUN_ARTIFACTS: round-a.tsv
#
# worker: ggml-rpc-server -d CUDA0 on srv2 (see rpc-split/_rpc.sh)
# python -m mcgyvr.serving.run --host srv1 --campaign pooled-slots \
#   --step tools/runs/campaigns/pooled-slots/1-round-a.sh \
#   --model /models/dense/Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf --ctx-per-slot 2048

[ -n "${RUN_ID:-}" ] || { echo "1-round-a.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_slots.sh disable=SC1091
. "$HERE/_slots.sh"

mapfile -t cells < <(slots_round a)
slots_serve round-a.tsv "${cells[@]}"

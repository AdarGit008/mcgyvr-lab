#!/usr/bin/env bash
# tools/runs/campaigns/srv1-multi-gpu/23-biggest-coder-fill.sh — step 23: the
# cells of step 22 that first sat at --n-cpu-moe 16 — below the measured
# two-card floor of 24 — and refused without measuring. Re-run at a placement
# that loads, so the axis is complete:
#
#   layer split  the two-card comparison step 22's walk left out (tensor split
#                 was measured; layer split was not)
#   one card      g0 at cm40: one card holds fewer expert blocks, so its floor
#                 is higher than the two-card 24; 8 blocks stay on the card
#   context       8k and 32k windows at the floor, with a ~90%-of-window
#                 prefill (@prefill), the long-window axis step 22's floor cell
#                 never reached
#   added cell    Qwen3-Next-80B-A3B Q3_K_M at cm24: brackets its floor between
#                 the cm16 refusal and the cm32 load already on file
#
# RUN_ARTIFACTS: biggest-coder-fill.tsv
#
# python -m mcgyvr.serving.run --host srv1 --campaign srv1-multi-gpu \
#   --step tools/runs/campaigns/srv1-multi-gpu/23-biggest-coder-fill.sh \
#   --model /models/dense/Qwen2.5-Coder-7B-Instruct-IQ4_XS.gguf --ctx-per-slot 2048

[ -n "${RUN_ID:-}" ] || { echo "23-biggest-coder-fill.sh: RUN_ID is unset — start me through the door: python -m mcgyvr.serving.run --host srv1 --campaign srv1-multi-gpu --step tools/runs/campaigns/srv1-multi-gpu/23-biggest-coder-fill.sh --model /models/dense/Qwen2.5-Coder-7B-Instruct-IQ4_XS.gguf --ctx-per-slot 2048" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_mgpu.sh disable=SC1091
. "$HERE/_mgpu.sh"

X=/models/moe
NEXT=$X/Qwen3-Coder-Next-UD-Q3_K_XL.gguf
NXTQ3=$X/Qwen3-Next-80B-A3B-Instruct-Q3_K_M.gguf
L="built:2048:1,4"

cells=(
    "next-l-cm24:$NEXT:layer:$L:--n-cpu-moe+24"
    "next-g0-cm40:$NEXT:g0:$L:--n-cpu-moe+40"
    "next-t-cm24-w8k:$NEXT:tensor:built:8192:1:@prefill=13600+--n-cpu-moe+24"
    "next-t-cm24-w32k:$NEXT:tensor:built:32768:1:@prefill=54600+--n-cpu-moe+24"
    "nxtq3-t-cm24:$NXTQ3:tensor:$L:--n-cpu-moe+24"
)

mgpu_serve biggest-coder-fill.tsv lcp "${cells[@]}"

#!/usr/bin/env bash
# tools/runs/campaigns/jev-mcorch/5-fill.sh — step 5: the capacity fill.
# The Jev unit (step 1's pick) resident on card 0, then the biggest
# orchestrator that still loads beside it: both cards, --n-cpu-moe walked
# DOWN from the step-22/23 floors (srv1-multi-gpu: Coder-Next tensor cm24,
# Qwen3-Next cm24) by the Jev's footprint, the refusal naming the edge
# (okf/must-read/touching-rigs.md: retry a refusal three times). Each
# placement that loads is driven by mgpu_sweep.py's @knob (sustained decode)
# and a PREFILL row (TTFT at ~1.5k tokens), so the fill is priced in what a
# conversational agent feels: TTFT and tpot with the Jev unit awake. The
# alternative placement — Jev on srv2 — is step 2 plus the no-Jev rows here.
# Cross-rig (--rpc to a ggml-rpc-server on srv2) is NOT in this step: pooled-
# slots and rpc-split already price it (-13..-29% decode, 3-4x TTFT), and a
# Jev on srv2's card leaves no RPC0 worth having.
#
# RUN_ARTIFACTS: fill.tsv
#
# python -m mcgyvr.serving.run --host srv1 --campaign jev-mcorch \
#   --step tools/runs/campaigns/jev-mcorch/5-fill.sh \
#   --model /data/moe/Qwen3-Coder-Next-UD-Q3_K_XL.gguf --ctx-per-slot 32768

[ -n "${RUN_ID:-}" ] || { echo "5-fill.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_jev.sh disable=SC1091
. "$HERE/_jev.sh"
# shellcheck source=../srv1-multi-gpu/_mgpu.sh disable=SC1091
. "$RUN_ROOT/tools/runs/campaigns/srv1-multi-gpu/_mgpu.sh"

jev_preamble fill.tsv
[ "$RUN_HOST" = srv1 ] || { _fail "REFUSED — the fill is srv1's two cards" || true; exit 2; }
open_tsv
jev_images
trap 'all_down; "$DOCKER" rm -f "$RUN_ID-mgpu-a" "$RUN_ID-mgpu-b" >/dev/null 2>&1 || true' EXIT
JEV=${JEV_MODEL:-/models/dense/Qwen3-4B-Q4_K_M.gguf}
if lcp_up jev device=0 "$JEV" 16384 --reasoning off; then
    emit unit_config jev
fi
emit workload_stamp tools/runs/workload.py
emit stamp NOTE "image=$LCP_IMG" "jev=$JEV" "jev_port=${JEV_PORT[jev]:-none}"
# cells: tag:model:layout:p2p:ctx:levels[:extra] (mgpu_sweep.py). The Jev
# unit's card-0 footprint is what moves the floor: cm24 loaded alone (step
# 22); the walk starts two above and goes down until the engine refuses.
CN=/data/moe/Qwen3-Coder-Next-UD-Q3_K_XL.gguf
C30=/models/moe/Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf
CTX=${ORCH_CTX:-32768}
cells=()
for cm in ${CNEXT_WALK:-28 26 24 22}; do
    cells+=("cnext-q3xl-cm$cm-jev:$CN:layer:built:$CTX:1:--n-cpu-moe+$cm+@prefill=2800+@knob")
done
cells+=("c30-q4xl-cm0-jev:$C30:layer:built:$CTX:1:@prefill=2800+@knob")
cells+=("c30-q4xl-cm0-jev-131k:$C30:layer:built:131072:1:@prefill=2800+@knob")
emit _py tools/runs/drivers/mgpu_sweep.py lcp "${cells[@]}"
# the same cells with the Jev unit down: what the Jev costs the orchestrator
unit_down jev
emit stamp NOTE "jev=down"
cells2=()
for cm in ${CNEXT_WALK_NOJEV:-24 22}; do
    cells2+=("cnext-q3xl-cm$cm-nojev:$CN:layer:built:$CTX:1:--n-cpu-moe+$cm+@prefill=2800+@knob")
done
cells2+=("c30-q4xl-cm0-nojev:$C30:layer:built:$CTX:1:@prefill=2800+@knob")
emit _py tools/runs/drivers/mgpu_sweep.py lcp "${cells2[@]}"
close_tsv
say "wrote $OUT"

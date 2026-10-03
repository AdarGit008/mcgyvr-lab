#!/usr/bin/env bash
# tools/runs/campaigns/jev-mcorch/0-fidelity.sh — step 0: what the engine
# hands decision.classify. One Jev candidate on llama.cpp and (JEV_NEED_VLLM=1)
# its AWQ twin on vLLM, probed with the product's exact request body on a
# fixed state: the first token's full top_logprobs, the label probabilities
# the primitive reads, and the warm max_tokens=1 wall. Three arms per engine
# where the template has a thinking block: the template as shipped (what the
# product sends today), `--reasoning off` on the server, and
# chat_template_kwargs {"enable_thinking": false} per request (which the
# product does NOT send; filed to show the template's effect). Pilot P0
# (records/evidence/2026-10-03-jev-mcorch/) found the shipped template answers
# `<think>` at p≈1.0 on Qwen3-4B and the primitive raises DecisionError on
# every question; `--reasoning off` fixes it with no code change.
#
# RUN_ARTIFACTS: fidelity.tsv
#
# python -m mcgyvr.serving.run --host srv1 --campaign jev-mcorch \
#   --step tools/runs/campaigns/jev-mcorch/0-fidelity.sh \
#   --model /models/dense/Qwen3-4B-Q4_K_M.gguf --ctx-per-slot 16384

[ -n "${RUN_ID:-}" ] || { echo "0-fidelity.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_jev.sh disable=SC1091
. "$HERE/_jev.sh"

jev_preamble fidelity.tsv
open_tsv
jev_images
trap all_down EXIT

M=${JEV_MODEL:-/models/dense/Qwen3-4B-Q4_K_M.gguf}
if lcp_up lcp-shipped device=0 "$M" 16384; then
    emit unit_config lcp-shipped
    emit _py "$HERE/jev_probe.py" lcp-shipped "${JEV_PORT[lcp-shipped]}" lcp-shipped
    emit _py "$HERE/jev_probe.py" lcp-shipped-kwargs "${JEV_PORT[lcp-shipped]}" lcp-shipped --kwargs '{"enable_thinking": false}'
    unit_down lcp-shipped
fi
if lcp_up lcp-rea-off device=0 "$M" 16384 --reasoning off; then
    emit unit_config lcp-rea-off
    emit _py "$HERE/jev_probe.py" lcp-rea-off "${JEV_PORT[lcp-rea-off]}" lcp-rea-off
    emit _py "$HERE/jev_probe.py" lcp-rea-off-pad4k "${JEV_PORT[lcp-rea-off]}" lcp-rea-off --pad 300
    unit_down lcp-rea-off
fi
if [ "${JEV_NEED_VLLM:-0}" = 1 ]; then
    V=${JEV_VLLM_MODEL:-thewimo/Qwen3-4B-AWQ}
    if vllm_up vllm-shipped device=0 "$V" 16384 --gpu-memory-utilization 0.6; then
        emit unit_config vllm-shipped
        emit _py "$HERE/jev_probe.py" vllm-shipped "${JEV_PORT[vllm-shipped]}" vllm-shipped
        emit _py "$HERE/jev_probe.py" vllm-shipped-kwargs "${JEV_PORT[vllm-shipped]}" vllm-shipped --kwargs '{"enable_thinking": false}'
        unit_down vllm-shipped
    fi
fi
close_tsv
say "wrote $OUT"

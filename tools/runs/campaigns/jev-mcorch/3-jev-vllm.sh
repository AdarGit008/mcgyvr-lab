#!/usr/bin/env bash
# tools/runs/campaigns/jev-mcorch/3-jev-vllm.sh — step 3: the in-VRAM Jev
# candidates on vLLM (AWQ safetensors from the rig's HF cache; vLLM's GGUF
# path is experimental, okf/must-read/touching-engine.md), srv1 card 0, the
# same slice and driver as step 1. The engine question: logprob fidelity
# (--logprobs-mode raw_logprobs, --max-logprobs 20), the warm max_tokens=1
# wall against llama.cpp's for the same checkpoint family, and the footprint
# a co-resident Jev costs the card (--gpu-memory-utilization is a share of the
# whole card: okf/config/vllm.md). Candidates: HF repo ids already cached
# (2-fetch of srv1-multi-gpu, or `huggingface-cli download` by hand first).
#
# RUN_ARTIFACTS: jev-vllm.tsv
#
# python -m mcgyvr.serving.run --host srv1 --campaign jev-mcorch \
#   --step tools/runs/campaigns/jev-mcorch/3-jev-vllm.sh \
#   --model /models/dense/Qwen3-4B-Q4_K_M.gguf --ctx-per-slot 16384

[ -n "${RUN_ID:-}" ] || { echo "3-jev-vllm.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_jev.sh disable=SC1091
. "$HERE/_jev.sh"

export JEV_NEED_VLLM=1
jev_preamble jev-vllm.tsv
open_tsv
jev_images
trap all_down EXIT
SLICE=${JEV_SLICE:-$HERE/slice-400.jsonl}
emit stamp SLICE "file=$(_tok "${SLICE#"$RUN_ROOT"/}")" "sha256=$(sha256sum "$SLICE" | cut -c1-16)"
UTIL=${JEV_VLLM_UTIL:-0.45}
LADDER=${JEV_VLLM_LADDER:-"
v-q25c-1.5b-awq=Qwen/Qwen2.5-Coder-1.5B-Instruct-AWQ
v-q25c-3b-awq=Qwen/Qwen2.5-Coder-3B-Instruct-AWQ
v-q3-4b-awq=thewimo/Qwen3-4B-AWQ
v-q25c-7b-awq=Qwen/Qwen2.5-Coder-7B-Instruct-AWQ
"}
for entry in $LADDER; do
    tag=${entry%%=*}
    model=${entry#*=}
    say "candidate $tag"
    extra=()
    case "$tag" in v-q3-*) extra=(--reasoning-parser qwen3 --default-chat-template-kwargs '{"enable_thinking": false}') ;; esac
    if vllm_up "$tag" device=0 "$model" 16384 --gpu-memory-utilization "$UTIL" "${extra[@]}"; then
        emit unit_config "$tag"
        emit _py "$HERE/jev_slice.py" "$tag" "${JEV_PORT[$tag]}" "$tag" "$SLICE"
        unit_down "$tag"
    fi
done
close_tsv
say "wrote $OUT"

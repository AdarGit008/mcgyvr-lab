#!/usr/bin/env bash
# tools/runs/campaigns/srv1-multi-gpu/22-biggest-coder.sh — step 22: the biggest
# coding checkpoint srv1 holds, Qwen3-Coder-Next-80B-A3B (qwen3next, ggufscan:
# 79.7B params, 48 layers, 512 experts x 10, 12 caching + 36 recurrent layers,
# n_ctx_train 262144, experts 33.7 GiB of a 36.3 GiB blob), and the general
# Qwen3-Next-80B-A3B-Instruct Q3_K_M fetched for this step (the same 79.7B
# shape). Both are bigger than anything in steps 1-21 and load only with most
# experts in host RAM, so this step is offload-bound like 18-offload.
#
#   capacity   the --n-cpu-moe floor: the tensor-split walk 0..48, and the
#              engine's refusal names the edge (one cell below the floor on
#              purpose). Offload cells are not fit-predicted (mgpu_sweep.py);
#              the sidecar's free_min_mib and swap_kib are the RAM evidence.
#   layers     the same walk IS the layer axis: more experts on the CPU means
#              more bytes read over DDR4-3600 per token, fewer over PCIe.
#   context    -c sweep at the floor (2048 / 8192 / 32768) on one level. KV is
#              cheap (12 caching layers of 48); the recurrent layers charge per
#              slot, so long windows are the cheap axis this architecture has.
#   MTP        NOT MEASURED HERE: ggufscan reads nextn_blocks=[] — llama.cpp
#              carries no MTP layers for qwen3next, so native multi-token
#              prediction is absent from these GGUF files. vLLM's Qwen3-Next
#              MTP path needs safetensors (BF16 ~160 GiB, AWQ ~44 GiB), out of
#              scope for a GGUF offload step.
#
# RUN_ARTIFACTS: biggest-coder.tsv
#
# python -m mcgyvr.serving.run --host srv1 --campaign srv1-multi-gpu \
#   --step tools/runs/campaigns/srv1-multi-gpu/22-biggest-coder.sh \
#   --model /models/dense/Qwen2.5-Coder-7B-Instruct-IQ4_XS.gguf --ctx-per-slot 2048

[ -n "${RUN_ID:-}" ] || { echo "22-biggest-coder.sh: RUN_ID is unset — start me through the door: python -m mcgyvr.serving.run --host srv1 --campaign srv1-multi-gpu --step tools/runs/campaigns/srv1-multi-gpu/22-biggest-coder.sh --model /models/dense/Qwen2.5-Coder-7B-Instruct-IQ4_XS.gguf --ctx-per-slot 2048" >&2; exit 2; }

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

cells=()
# capacity + layers: the --n-cpu-moe walk on tensor split (both cards)
for n in 0 8 16 24 32 40 48; do
    cells+=("next-t-cm$n:$NEXT:tensor:$L:--n-cpu-moe+$n")
done
# layer split as the two-card comparison, and one card (g0) as the baseline a
# two-card split has to beat. The two-card floor is 24; one card holds fewer
# expert blocks, so its floor is higher — cm40 keeps 8 blocks on the card.
cells+=(
    "next-l-cm24:$NEXT:layer:$L:--n-cpu-moe+24"
    "next-g0-cm40:$NEXT:g0:$L:--n-cpu-moe+40"
)
# context at the floor: a PREFILL prompt of ~90% of the window (@prefill,
# ~0.54 tokens a character) so the long window is actually exercised, not just
# allocated. KV is 12 caching layers of 48; the recurrent layers charge per slot.
cells+=(
    "next-t-cm24-w8k:$NEXT:tensor:built:8192:1:@prefill=13600+--n-cpu-moe+24"
    "next-t-cm24-w32k:$NEXT:tensor:built:32768:1:@prefill=54600+--n-cpu-moe+24"
)
# the added general 80B, at two placements (its fetch may still be in flight —
# the engine's refusal is the record until it lands)
cells+=(
    "nxtq3-t-cm24:$NXTQ3:tensor:$L:--n-cpu-moe+24"
    "nxtq3-t-cm32:$NXTQ3:tensor:$L:--n-cpu-moe+32"
)

mgpu_serve biggest-coder.tsv lcp "${cells[@]}"

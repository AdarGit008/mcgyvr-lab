#!/usr/bin/env bash
# tools/runs/campaigns/jev-mcorch/1-jev-ladder.sh — step 1: the Jev candidate
# ladder over the labelled slice, llama.cpp, one card (device=0), one slot.
# Each candidate is launched, probed over every slice row through
# decision.classify (jev_slice.py: gate/jev.py's three questions and
# verify.py's verdict), and torn down before the next. Rows are ROW per slice
# row and one SUMMARY per candidate; the SUMMARY's auroc/brier/ece are read
# against the pilot's (records/evidence/2026-10-03-jev-mcorch/p1-*.jsonl).
# Candidates are container paths; a path the rig does not hold files REFUSED.
# JEV_LADDER overrides the list (space-separated TAG=PATH[+flag+flag]).
#
# RUN_ARTIFACTS: jev-ladder.tsv
#
# python -m mcgyvr.serving.run --host srv1 --campaign jev-mcorch \
#   --step tools/runs/campaigns/jev-mcorch/1-jev-ladder.sh \
#   --model /models/dense/Qwen3-4B-Q4_K_M.gguf --ctx-per-slot 16384

[ -n "${RUN_ID:-}" ] || { echo "1-jev-ladder.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_jev.sh disable=SC1091
. "$HERE/_jev.sh"

jev_preamble jev-ladder.tsv
open_tsv
jev_images
trap all_down EXIT

SLICE=${JEV_SLICE:-$HERE/slice-400.jsonl}
emit stamp SLICE "file=$(_tok "${SLICE#"$RUN_ROOT"/}")" "sha256=$(sha256sum "$SLICE" | cut -c1-16)"
GPUS=${JEV_GPUS:-device=0}
# TAG=PATH[+flag...]; thinking-by-default templates carry --reasoning off (step 0).
LADDER=${JEV_LADDER:-"
q25c-1.5b-q4km=/models/dense/Qwen2.5-Coder-1.5B-Instruct-Q4_K_M.gguf
q25c-3b-q4km=/models/dense/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf
q3-4b-q4km=/models/dense/Qwen3-4B-Q4_K_M.gguf+--reasoning+off
q3-4b-2507-q4km=/models/dense/Qwen3-4B-Instruct-2507-Q4_K_M.gguf
q35-2b-q8=/models/dense/Qwen3.5-2B-Q8_0.gguf
q35-4b-q4km=/models/dense/Qwen3.5-4B-Q4_K_M.gguf+--reasoning+off
gemma3-4b-q4km=/models/dense/gemma-3-4b-it-Q4_K_M.gguf
q25c-7b-iq4xs=/models/dense/Qwen2.5-Coder-7B-Instruct-IQ4_XS.gguf
q3-8b-q4km=/models/dense/Qwen3-8B-Q4_K_M.gguf+--reasoning+off
q35-9b-q4km=/models/dense/Qwen3.5-9B-Q4_K_M.gguf+--reasoning+off
q25c-14b-q4km=/models/dense/Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf
"}
for entry in $LADDER; do
    tag=${entry%%=*}
    rest=${entry#*=}
    model=${rest%%+*}
    flags=()
    if [ "$rest" != "$model" ]; then
        IFS='+' read -r -a flags <<<"${rest#*+}"
    fi
    say "candidate $tag"
    if lcp_up "$tag" "$GPUS" "$model" 16384 "${flags[@]}"; then
        emit unit_config "$tag"
        emit _py "$HERE/jev_slice.py" "$tag" "${JEV_PORT[$tag]}" "$tag" "$SLICE"
        unit_down "$tag"
    fi
done
close_tsv
say "wrote $OUT"

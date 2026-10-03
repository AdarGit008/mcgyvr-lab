#!/usr/bin/env bash
# tools/runs/campaigns/jev-mcorch/8-jev-items.sh — step 8: the Jev candidates
# over the labelled items (owner answer 3, 2026-10-03): J1 intent, J2
# ready_to_run, J3 next, in_scope and regression_risk, 60 items each, drawn
# from the step-6 transcripts and labelled by an Opus subagent (the items
# file names its provenance and the 10% spot-check sample). Same launch
# shape as step 1, one card, one slot; the ITEMS file is JEV_ITEMS.
#
# RUN_ARTIFACTS: jev-items.tsv
#
# python -m mcgyvr.serving.run --host srv1 --campaign jev-mcorch \
#   --step tools/runs/campaigns/jev-mcorch/8-jev-items.sh \
#   --model /models/dense/Qwen3-4B-Q4_K_M.gguf --ctx-per-slot 16384

[ -n "${RUN_ID:-}" ] || { echo "8-jev-items.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_jev.sh disable=SC1091
. "$HERE/_jev.sh"

jev_preamble jev-items.tsv
open_tsv
jev_images
trap all_down EXIT
ITEMS=${JEV_ITEMS:-$HERE/items-2026-10-03.jsonl}
[ -f "$ITEMS" ] || { _fail "REFUSED — no items file at $ITEMS" || true; exit 2; }
emit stamp ITEMS "file=$(_tok "${ITEMS#"$RUN_ROOT"/}")" "sha256=$(sha256sum "$ITEMS" | cut -c1-16)" "n=$(grep -c '"question"' "$ITEMS")"
GPUS=${JEV_GPUS:-device=0}
LADDER=${JEV_LADDER:-"
q25c-1.5b-q4km=/models/dense/Qwen2.5-Coder-1.5B-Instruct-Q4_K_M.gguf
q35-2b-q8=/models/dense/Qwen3.5-2B-Q8_0.gguf
q3-4b-2507-q4km=/models/dense/Qwen3-4B-Instruct-2507-Q4_K_M.gguf
q35-4b-q4km=/models/dense/Qwen3.5-4B-Q4_K_M.gguf
gemma3-4b-q4km=/models/dense/gemma-3-4b-it-Q4_K_M.gguf
q3-8b-q4km=/models/dense/Qwen3-8B-Q4_K_M.gguf
q35-9b-q4km=/models/dense/Qwen3.5-9B-Q4_K_M.gguf
q25c-14b-q4km=/models/dense/Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf
c30-a3b-q4xl=/models/moe/Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf+-sm+layer
"}
for entry in $LADDER; do
    tag=${entry%%=*}
    rest=${entry#*=}
    model=${rest%%+*}
    flags=()
    if [ "$rest" != "$model" ]; then
        IFS='+' read -r -a flags <<<"${rest#*+}"
    fi
    gpus=$GPUS
    case "$tag" in c30-*) gpus=all ;; esac
    say "candidate $tag"
    if lcp_up "$tag" "$gpus" "$model" 16384 "${flags[@]}"; then
        emit unit_config "$tag"
        emit _py "$HERE/jev_items.py" "$tag" "${JEV_PORT[$tag]}" "$tag" "$ITEMS"
        unit_down "$tag"
    fi
done
close_tsv
say "wrote $OUT"

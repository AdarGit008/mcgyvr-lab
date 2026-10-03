#!/usr/bin/env bash
# tools/runs/campaigns/jev-mcorch/2-jev-srv2.sh — step 2: step 1's ladder on
# srv2's card (the GTX 1660 SUPER as of 2026-09-27, read live by gate 2),
# llama.cpp on the same image. The placement question: a Jev that lives on
# srv2 leaves srv1's two cards whole for the orchestrator (step 5). Only the
# candidates that fit a 6 GB card with a 16k window are offered; the engine's
# refusal names the edge. Same slice, same driver, so SUMMARY rows compare
# with step 1's on wall_row_med_s — the quality figures are the model's and
# must agree within the tolerance class, or the card changed the answer.
#
# RUN_ARTIFACTS: jev-srv2.tsv
#
# python -m mcgyvr.serving.run --host srv2 --campaign jev-mcorch \
#   --step tools/runs/campaigns/jev-mcorch/2-jev-srv2.sh \
#   --model /models/dense/Qwen3-4B-Q4_K_M.gguf --ctx-per-slot 16384

[ -n "${RUN_ID:-}" ] || { echo "2-jev-srv2.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_jev.sh disable=SC1091
. "$HERE/_jev.sh"

[ "$RUN_HOST" = srv2 ] || { _fail "REFUSED — step 2 is srv2's, and the run is on $RUN_HOST" || true; exit 2; }
export JEV_LADDER=${JEV_LADDER:-"
q25c-1.5b-q4km=/models/dense/Qwen2.5-Coder-1.5B-Instruct-Q4_K_M.gguf
q25c-3b-q4km=/models/dense/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf
q3-4b-q4km=/models/dense/Qwen3-4B-Q4_K_M.gguf+--reasoning+off
q3-4b-2507-q4km=/models/dense/Qwen3-4B-Instruct-2507-Q4_K_M.gguf
q35-2b-q8=/models/dense/Qwen3.5-2B-Q8_0.gguf
q35-4b-q4km=/models/dense/Qwen3.5-4B-Q4_K_M.gguf+--reasoning+off
q25c-7b-iq4xs=/models/dense/Qwen2.5-Coder-7B-Instruct-IQ4_XS.gguf
"}
# The ladder step's body, with this host's card: one script, two hosts.
jev_preamble jev-srv2.tsv
open_tsv
jev_images
trap all_down EXIT
SLICE=${JEV_SLICE:-$HERE/slice-400.jsonl}
emit stamp SLICE "file=$(_tok "${SLICE#"$RUN_ROOT"/}")" "sha256=$(sha256sum "$SLICE" | cut -c1-16)"
for entry in $JEV_LADDER; do
    tag=${entry%%=*}
    rest=${entry#*=}
    model=${rest%%+*}
    flags=()
    if [ "$rest" != "$model" ]; then
        IFS='+' read -r -a flags <<<"${rest#*+}"
    fi
    say "candidate $tag"
    if lcp_up "$tag" device=0 "$model" 16384 "${flags[@]}"; then
        emit unit_config "$tag"
        emit _py "$HERE/jev_slice.py" "$tag" "${JEV_PORT[$tag]}" "$tag" "$SLICE"
        unit_down "$tag"
    fi
done
close_tsv
say "wrote $OUT"

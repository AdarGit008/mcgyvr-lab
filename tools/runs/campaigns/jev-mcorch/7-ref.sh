#!/usr/bin/env bash
# tools/runs/campaigns/jev-mcorch/7-ref.sh — step 7: the API-tier reference arm
# (owner answer 4, 2026-10-03: approved, kept small). The same corpus as steps
# 4 and 6, one hosted model, three measurements: D and P (orch_modes.py) and
# the agent loop (tool_loop.py), each row carrying the tokens and the cost at
# the prices below. The door is opened on srv1 so the run has an envelope and
# a round like every other step; nothing is launched on the rig and no Jev is
# co-resident — the arm is a ceiling for the contract-authoring and loop
# scores, not a placement. The credential is the environment variable named
# by REF_KEY_ENV, read by the drivers and never printed; with the variable
# unset the step files REFUSED and ends.
#
# RUN_ARTIFACTS: ref.tsv
#
# python -m mcgyvr.serving.run --host srv1 --campaign jev-mcorch \
#   --step tools/runs/campaigns/jev-mcorch/7-ref.sh \
#   --model /models/dense/Qwen3-4B-Q4_K_M.gguf --ctx-per-slot 16384

[ -n "${RUN_ID:-}" ] || { echo "7-ref.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_jev.sh disable=SC1091
. "$HERE/_jev.sh"

jev_preamble ref.tsv
open_tsv
REF_MODEL=${REF_MODEL:-claude-opus-5-5}
REF_KEY_ENV=${REF_KEY_ENV:-ANTHROPIC_API_KEY}
# USD per million tokens, the first-party rate card the claude-api skill
# carries for this model id (cached 2026-09-25): input 4.00, output 20.00.
REF_PRICE_IN=${REF_PRICE_IN:-4.00}
REF_PRICE_OUT=${REF_PRICE_OUT:-20.00}
emit stamp NOTE "ref_model=$REF_MODEL" "key_env=$REF_KEY_ENV" "price_in_usd_per_m=$REF_PRICE_IN" "price_out_usd_per_m=$REF_PRICE_OUT" "transport=anthropic-messages-raw-http"
if [ -z "${!REF_KEY_ENV:-}" ]; then
    emit refused ref "model=$REF_MODEL" -- "$REF_KEY_ENV is not set in the operator's environment; the Ref arm is skipped"
    close_tsv
    exit 0
fi
REPOS="$RUN_OUT_DIR/repos"
REAL=()
[ -n "${ORCH_REAL_REPO:-}" ] && REAL=(--real "mcgyvr=$ORCH_REAL_REPO")
# shellcheck disable=SC2086
_py "$HERE/make_repos.py" "$REPOS" ${ORCH_TASKS:-b002-option-pairs b003-carve-shift b004-install-order b073-bump-release b252-swipe-dedupe} "${REAL[@]}" ||
    { _fail "REFUSED — make_repos.py could not build the corpus" || true; exit 2; }
emit stamp CORPUS "tasks=$(_tok "${ORCH_TASKS:-b002-option-pairs,b003-carve-shift,b004-install-order,b073-bump-release,b252-swipe-dedupe}")" "real=$(_tok "${ORCH_REAL_REPO:-none}")"
work="$RUN_OUT_DIR/work-ref"
tag="api-$(_tok "$REF_MODEL")"
emit _py "$HERE/orch_modes.py" "$tag" 0 "$REF_MODEL" "$REPOS" "$work" --modes D,P --api anthropic --api-key-env "$REF_KEY_ENV" --price-in "$REF_PRICE_IN" --price-out "$REF_PRICE_OUT"
MCGYVR_CONFIG="$work/cfg" emit _py "$HERE/tool_loop.py" "$tag" 0 "$REF_MODEL" "$REPOS" "$work/loops" --max-turns "${ORCH_TURNS:-20}" --api anthropic --api-key-env "$REF_KEY_ENV" --price-in "$REF_PRICE_IN" --price-out "$REF_PRICE_OUT"
close_tsv
say "wrote $OUT"

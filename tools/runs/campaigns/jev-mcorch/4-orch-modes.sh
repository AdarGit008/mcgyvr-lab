#!/usr/bin/env bash
# tools/runs/campaigns/jev-mcorch/4-orch-modes.sh — step 4: the orchestrator
# modes per orchestrator candidate. One candidate at a time across srv1's two
# cards (layer split; --n-cpu-moe where the checkpoint needs it), with the Jev
# unit of step 1's best candidate co-resident on card 0 when JEV_MODEL is set
# (the verifier role and J's typed choices are bound to it; D and P to the
# orchestrator). orch_modes.py runs D (schema in context), P (`mcgyvr
# delegate`, proposer_for) and J (classifier_proposer_for through decompose,
# wired here because cli.py does not) over every repo under REPOS, then
# `mcgyvr run` on each emitted contract (--run). MODE rows per (repo, mode),
# RUN rows per contract. The orchestrator's wall is TTFT-bound on the
# schema-in-context arm (SKILL.md is ~5k tokens): read prompt_tokens with it.
#
# RUN_ARTIFACTS: orch-modes.tsv
#
# python -m mcgyvr.serving.run --host srv1 --campaign jev-mcorch \
#   --step tools/runs/campaigns/jev-mcorch/4-orch-modes.sh \
#   --model /models/moe/Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf --ctx-per-slot 32768

[ -n "${RUN_ID:-}" ] || { echo "4-orch-modes.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_jev.sh disable=SC1091
. "$HERE/_jev.sh"

jev_preamble orch-modes.tsv
open_tsv
jev_images
trap all_down EXIT
REPOS="$RUN_OUT_DIR/repos"
# the corpus is made into the envelope at run time: one git repo per bench task
_py "$HERE/make_repos.py" "$REPOS" ${ORCH_TASKS:-b002-option-pairs b003-carve-shift b004-install-order b073-bump-release b252-swipe-dedupe} ||
    { _fail "REFUSED — make_repos.py could not build the corpus" || true; exit 2; }
emit stamp CORPUS "tasks=$(_tok "${ORCH_TASKS:-b002-option-pairs,b003-carve-shift,b004-install-order,b073-bump-release,b252-swipe-dedupe}")"
JEV_ARGS=()
if [ -n "${JEV_MODEL:-}" ]; then
    if lcp_up jev device=0 "$JEV_MODEL" 16384 --reasoning off; then
        emit unit_config jev
        JEV_ARGS=(--jev-port "${JEV_PORT[jev]}" --jev-model jev)
    fi
fi
# TAG=PATH[+flag...]: the orchestrator candidates, both cards, layer split.
LADDER=${ORCH_LADDER:-"
c30-a3b-q4xl=/models/moe/Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf+-sm+layer
c30-a3b-iq3xxs=/data/moe/Qwen3-Coder-30B-A3B-Instruct-UD-IQ3_XXS.gguf+-sm+layer
q36-35b-iq3xxs=/models/moe/Qwen3.6-35B-A3B-UD-IQ3_XXS.gguf+-sm+layer+--reasoning+off
glm47-flash-q4xl=/models/moe/GLM-4.7-Flash-UD-Q4_K_XL.gguf+-sm+layer+--reasoning+off
gptoss-20b-mxfp4=/models/moe/gpt-oss-20b-MXFP4.gguf+-sm+layer+--reasoning-effort+low
cnext-80b-q3xl=/data/moe/Qwen3-Coder-Next-UD-Q3_K_XL.gguf+-sm+layer+--n-cpu-moe+24
"}
CTX=${ORCH_CTX:-32768}
for entry in $LADDER; do
    tag=${entry%%=*}
    rest=${entry#*=}
    model=${rest%%+*}
    flags=()
    if [ "$rest" != "$model" ]; then
        IFS='+' read -r -a flags <<<"${rest#*+}"
    fi
    say "orchestrator $tag"
    if lcp_up "$tag" all "$model" "$CTX" "${flags[@]}"; then
        emit unit_config "$tag"
        emit _py "$HERE/orch_modes.py" "$tag" "${JEV_PORT[$tag]}" "$tag" "$REPOS" "$RUN_OUT_DIR/work-$tag" --run "${JEV_ARGS[@]}"
        unit_down "$tag"
    fi
done
close_tsv
say "wrote $OUT"

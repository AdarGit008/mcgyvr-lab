#!/usr/bin/env bash
# tools/runs/campaigns/jev-mcorch/6-tool-loop.sh — step 6: the rung AS the
# conversational agent. Per orchestrator candidate (both cards, layer split),
# tool_loop.py plays the harness: the compact mcorch prompt, the four tools
# (read_file, write_file, bash, grep) over OpenAI chat/completions with
# `tools`, and the rung's tool calls executed in a clone of each repo under
# REPOS — write contract.yaml, `mcgyvr contract`, `mcgyvr run --repo .`, read
# the result, replan, finish in plain text. The engine parses the tool calls
# (--jinja and the GGUF's template; the flags are on the LAUNCH row). TURN rows
# carry wall, prompt/completion/cached tokens; LOOP rows the outcome. Then the
# context ladder (CTX rows): a cold mcorch-shaped transcript at 4k..64k tokens
# and the same transcript plus one tool turn, so prompt processing and
# prefix-cache reuse are priced per candidate. MCGYVR_CONFIG is the config
# orch_modes.write_config writes (the same unit is the ladder's rung), so the
# `mcgyvr run` the rung emits lands on itself: the skill flow on a local model.
#
# RUN_ARTIFACTS: tool-loop.tsv
#
# python -m mcgyvr.serving.run --host srv1 --campaign jev-mcorch \
#   --step tools/runs/campaigns/jev-mcorch/6-tool-loop.sh \
#   --model /models/moe/Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf --ctx-per-slot 65536

[ -n "${RUN_ID:-}" ] || { echo "6-tool-loop.sh: RUN_ID is unset — start me through the door" >&2; exit 2; }

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../../_common.sh disable=SC1091
. "$HERE/../../_common.sh"
door_required
# shellcheck source=./_jev.sh disable=SC1091
. "$HERE/_jev.sh"

jev_preamble tool-loop.tsv
open_tsv
jev_images
trap all_down EXIT
REPOS="$RUN_OUT_DIR/repos"
# the corpus is made into the envelope at run time: one git repo per bench task
_py "$HERE/make_repos.py" "$REPOS" ${ORCH_TASKS:-b002-option-pairs b003-carve-shift b004-install-order b073-bump-release b252-swipe-dedupe} ||
    { _fail "REFUSED — make_repos.py could not build the corpus" || true; exit 2; }
emit stamp CORPUS "tasks=$(_tok "${ORCH_TASKS:-b002-option-pairs,b003-carve-shift,b004-install-order,b073-bump-release,b252-swipe-dedupe}")"
LADDER=${ORCH_LADDER:-"
c30-a3b-q4xl=/models/moe/Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf+-sm+layer
q36-35b-iq3xxs=/models/moe/Qwen3.6-35B-A3B-UD-IQ3_XXS.gguf+-sm+layer+--reasoning+off
glm47-flash-q4xl=/models/moe/GLM-4.7-Flash-UD-Q4_K_XL.gguf+-sm+layer+--reasoning+off
gptoss-20b-mxfp4=/models/moe/gpt-oss-20b-MXFP4.gguf+-sm+layer+--reasoning-effort+low
cnext-80b-q3xl=/data/moe/Qwen3-Coder-Next-UD-Q3_K_XL.gguf+-sm+layer+--n-cpu-moe+24
"}
CTX=${ORCH_CTX:-65536}
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
        work="$RUN_OUT_DIR/work-$tag"
        # the config the rung's own `mcgyvr run` lands on
        _py "$HERE/orch_modes.py" --write-config-only "$tag" "${JEV_PORT[$tag]}" "$tag" "$REPOS" "$work" >/dev/null
        MCGYVR_CONFIG="$work/cfg" emit _py "$HERE/tool_loop.py" "$tag" "${JEV_PORT[$tag]}" "$tag" "$REPOS" "$work/loops" --max-turns "${ORCH_TURNS:-20}"
        emit _py "$HERE/tool_loop.py" "$tag" "${JEV_PORT[$tag]}" "$tag" --ctx-ladder "${ORCH_CTX_LADDER:-4096,8192,16384,32768,65536}"
        unit_down "$tag"
    fi
done
close_tsv
say "wrote $OUT"

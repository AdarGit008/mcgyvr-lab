#!/usr/bin/env bash
# chain.sh STEP[:SUFFIX] ... — run pooled-slots steps through the door one
# after another, filing the worker before and after each; stop at the first
# step that does not exit 0.
SP=/tmp/claude-1000/-home-adaramir-claude-mcgyvr-lab-open-issues/87def55d-87d9-44ae-ae4a-6fba1f6fdcc1/scratchpad
LAB=/home/adaramir/claude/mcgyvr-lab-open-issues/.claude/worktrees/agent-a3f7b1468a0872694
cd "$LAB" || exit 1
for spec in "$@"; do
    step=${spec%%:*}
    suffix=""
    [ "$spec" != "$step" ] && suffix=${spec#*:}
    name=$(basename "$step" .sh)
    bash "$SP/worker.sh" "before-$name${suffix:+-$suffix}" >/dev/null
    log="$SP/door-$name${suffix:+-$suffix}.log"
    MCGYVR_RUN_ROOT="$LAB" uv run --no-sync python -m mcgyvr.serving.run --host srv1 \
        --campaign pooled-slots --step "tools/runs/campaigns/pooled-slots/$step" \
        ${suffix:+--suffix "$suffix"} \
        --model /models/dense/Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf --ctx-per-slot 2048 \
        >"$log" 2>&1
    rc=$?
    echo "exit=$rc" >>"$log"
    bash "$SP/worker.sh" "after-$name${suffix:+-$suffix}" >/dev/null
    echo "$(date -u +%FT%TZ) $spec exit=$rc" >>"$SP/chain.log"
    [ "$rc" = 0 ] || exit "$rc"
done
echo "$(date -u +%FT%TZ) chain done" >>"$SP/chain.log"

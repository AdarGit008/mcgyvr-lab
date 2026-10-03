#!/usr/bin/env bash
set -uo pipefail
S=/tmp/claude-1000/-home-adaramir/15b6132f-a502-4a0c-9d7f-4c7b9b894f37/scratchpad/run; MC=/tmp/claude-1000/-home-adaramir/15b6132f-a502-4a0c-9d7f-4c7b9b894f37/scratchpad/wt/mc-run
LOG=$S/p3b-orch.log; : >"$LOG"
true
cmd='docker run -d --name orch-p3 --gpus all -v $HOME/models:/models:ro -v /data/models:/data:ro -p 8080:8080 llamacpp:b10644-L3-rpc --model /data/moe/Qwen3-Coder-30B-A3B-Instruct-UD-IQ3_XXS.gguf -sm layer -c 32768 -np 1 --jinja -lv 4 --no-warmup --host 0.0.0.0 --port 8080 -a orch'
echo "launch: $cmd" | tee -a "$LOG"
ssh -n srv1 "$cmd" >/dev/null
for i in $(seq 1 300); do curl -sf -m 2 http://srv1:8080/health >/dev/null 2>&1 && break; sleep 1; done
curl -s http://srv1:8080/health | tee -a "$LOG"; echo
cd $MC
for r in b002-option-pairs b004-install-order b252-swipe-dedupe; do
  echo "=== tool-loop $r $(date -u +%T)" | tee -a "$LOG"
  uv run --no-sync python $S/tool_loop.py http://srv1:8080 orch lcp-c30-a3b-iq3xxs-layer2-32k $S/p2repos/$r $S/p3-toolloop.jsonl --cfg $S/p2cfg 2>&1 | tail -3 | tee -a "$LOG"
done
cd $MC && uv run --no-sync python $S/p2_run.py $S/p2cfg $S/p2repos $S/p2-modes-pj.jsonl lcp-c30-a3b-iq3xxs-layer2-32k --modes P,J 2>&1 | tee -a "$LOG"
ssh -n srv1 'docker rm -f orch-p3 >/dev/null 2>&1; nvidia-smi --query-gpu=index,memory.used --format=csv,noheader' | tee -a "$LOG"
echo "done $(date -u +%T)" | tee -a "$LOG"

#!/usr/bin/env bash
# P1 sweep: launch each Jev candidate on srv1 by hand (pilot stage), run
# p1_run.py over the slice, tear down. One container at a time, name jev-p0.
# Each line of models.txt: TAG|GPUS|CONTAINER_MODEL_PATH|EXTRA_FLAGS
set -uo pipefail
S=/tmp/claude-1000/-home-adaramir/15b6132f-a502-4a0c-9d7f-4c7b9b894f37/scratchpad/run
MC=/tmp/claude-1000/-home-adaramir/15b6132f-a502-4a0c-9d7f-4c7b9b894f37/scratchpad/wt/mc-run
IMG=llamacpp:b10644-L3-rpc
HOST=${HOST:-srv1}
PORT=${PORT:-8080}
SLICE=${SLICE:-$S/slice-p1.jsonl}
LOG=$S/p1-sweep-$HOST.log
: >"$LOG"
while IFS='|' read -r tag gpus model extra; do
    [ -z "$tag" ] && continue
    case "$tag" in \#*) continue;; esac
    echo "=== $tag $(date -u +%FT%TZ)" | tee -a "$LOG"
    ssh -n "$HOST" "docker rm -f jev-p0 >/dev/null 2>&1; true"
    cmd="docker run -d --name jev-p0 --gpus $gpus -v \$HOME/models:/models:ro ${DATA_MOUNT:--v /data/models:/data:ro} -p $PORT:8080 $IMG --model $model -c 16384 -np 1 --jinja -lv 4 --no-warmup --host 0.0.0.0 --port 8080 -a jev $extra"
    echo "launch: $cmd" | tee -a "$LOG"
    t0=$(date +%s)
    ssh -n "$HOST" "$cmd" >/dev/null || { echo "launch failed" | tee -a "$LOG"; continue; }
    ok=""
    for i in $(seq 1 240); do
        curl -sf -m 2 "http://$HOST:$PORT/health" >/dev/null 2>&1 && ok=1 && break
        sleep 1
    done
    if [ -z "$ok" ]; then
        echo "REFUSED: no /health in 240 s" | tee -a "$LOG"
        ssh -n "$HOST" "docker logs jev-p0 2>&1 | tail -5" | tee -a "$LOG"
        ssh -n "$HOST" "docker rm -f jev-p0 >/dev/null 2>&1; true"
        continue
    fi
    echo "load_s=$(( $(date +%s) - t0 ))" | tee -a "$LOG"
    ssh -n "$HOST" "nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' '; docker logs jev-p0 2>&1 | grep -E 'load_tensors: +(CUDA|CPU)[0-9]* model buffer|llama_kv_cache: +CUDA|n_ctx_per_seq' | head -6" | tee -a "$LOG"
    (cd "$MC" && uv run --no-sync python "$S/p1_run.py" "http://$HOST:$PORT" jev "$tag" "$SLICE" "$S/p1-$tag.jsonl") 2>&1 | tail -1 | tee -a "$LOG"
    ssh -n "$HOST" "docker rm -f jev-p0 >/dev/null 2>&1; true"
done <"${1:-$S/models.txt}"
ssh -n "$HOST" "nvidia-smi --query-gpu=index,memory.used --format=csv,noheader" | tee -a "$LOG"
echo "done $(date -u +%FT%TZ)" | tee -a "$LOG"

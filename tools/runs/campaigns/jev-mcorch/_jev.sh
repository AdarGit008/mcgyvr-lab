# shellcheck shell=bash
# tools/runs/campaigns/jev-mcorch/_jev.sh — what every step of jev-mcorch
# shares, sourced after tools/runs/_common.sh. Executes nothing.
#
#   jev_preamble ARTIFACT    the refusals every step makes before it writes:
#                            the host is srv1 or srv2 (both appear in
#                            hosts.json); sets OUT, DOCKER, SSH, CARDS.
#   emit CMD...              CMD's stdout appended to OUT
#   say TEXT...              progress on stderr, never in the artifact
#   open_tsv                 the stamps a door-produced TSV opens with, and one
#                            GPU row per card the host shows
#   close_tsv                ### END, then the start==end comparison
#   lcp_up NAME GPUS MODEL CTX EXTRA...
#                            llama-server from the resolved digest, container
#                            $RUN_ID-jev-NAME, port JEV_PORT[NAME]; waits for
#                            /health on the rig (240 s) or files REFUSED and
#                            returns 1. One slot (-np 1): a Jev call is
#                            sequential by construction (decision.classify).
#   vllm_up NAME GPUS MODEL CTX EXTRA...
#                            vllm serve from the resolved digest, same contract.
#                            --max-logprobs 20 (the OpenAI cap the product
#                            assumes), --dtype float16, --logprobs-mode
#                            raw_logprobs (the default, spelled).
#   unit_down NAME           docker rm -f; waits for the card to settle.
#   unit_config NAME         CONFIG row: the engine's own buffer lines (-lv 4)
#                            and card memory after load.
#
# THE MODELS ARE READ, NOT DECLARED. A step names container paths under
# /models (the rig's ~/models) and /data (srv1's /data/models); lcp_up refuses
# a path the rig does not hold rather than letting the engine's "no such file"
# read as a model that failed to load.

OUT=""
DOCKER=""
SSH=""
CARDS=""
declare -A JEV_PORT=()
declare -A JEV_NAME=()
_NEXT_PORT=8096

say() { printf 'jev-mcorch: %s\n' "$*" >&2; }

emit() { "$@" >>"$OUT"; }

jev_preamble() {
    local artifact=$1
    DOCKER=$(_door_shim docker) || exit 2
    SSH=$(_door_shim ssh) || exit 2
    OUT="$RUN_OUT_DIR/$artifact"
    case "$RUN_HOST" in
        srv1 | srv2) ;;
        *) _fail "REFUSED — this campaign runs on srv1 or srv2, and the run is on $RUN_HOST" || true; exit 2 ;;
    esac
    CARDS=$("$SSH" "$RUN_HOST" 'nvidia-smi --query-gpu=index --format=csv,noheader | wc -l' </dev/null) ||
        { _fail "REFUSED — $RUN_HOST's cards could not be counted" || true; exit 2; }
    [ "$CARDS" -ge 1 ] || { _fail "REFUSED — $RUN_HOST shows no card" || true; exit 2; }
}

gpu_rows() {
    "$SSH" "$RUN_HOST" 'nvidia-smi --query-gpu=index,name,pci.bus_id,memory.total,memory.free,compute_cap,power.limit,pcie.link.gen.max,pcie.link.width.max,driver_version --format=csv,noheader,nounits' </dev/null |
        while IFS=, read -r idx name bus total free cc plimit gmax wmax drv; do
            row "gpu$(_tok "$idx")" GPU \
                "index=$(_tok "$idx")" "name=$(_tok "$name")" "bus=$(_tok "$bus")" \
                "vram_mib=$(_tok "$total")" "free_mib=$(_tok "$free")" "cc=$(_tok "$cc")" \
                "power_limit_w=$(_tok "$plimit")" "pcie_gen_max=$(_tok "$gmax")" \
                "pcie_width_max=$(_tok "$wmax")" "driver=$(_tok "$drv")"
        done
}

host_row() {
    local avail
    avail=$("$SSH" "$RUN_HOST" "awk '/MemAvailable/ {print \$2}' /proc/meminfo" </dev/null)
    row host HOST "mem_available_kib=$(_tok "$avail")" "nproc=$("$SSH" "$RUN_HOST" nproc </dev/null)"
}

open_tsv() {
    : >"$OUT"
    emit start_stamp
    emit round_stamp
    emit rig_stamp
    emit gpu_rows
    emit host_row
}

close_tsv() {
    emit end_stamp
    rig_assert_unchanged
}

_model_present() {
    # /models/... is the rig's ~/models; /data/... is srv1's /data/models.
    local path=$1 rig_path
    case "$path" in
        /models/*) rig_path="\$HOME/models/${path#/models/}" ;;
        /data/*) rig_path="/data/models/${path#/data/}" ;;
        *) return 1 ;;
    esac
    "$SSH" "$RUN_HOST" "test -e $rig_path" </dev/null
}

_wait_health() {
    local name=$1 port=$2 path=$3 i
    for i in $(seq 1 240); do
        # polled from here, at the rig's address: the container runs on the rig
        if curl -sf -m 2 "http://$RUN_HOST:$port$path" >/dev/null 2>&1; then
            return 0
        fi
        if ! "$DOCKER" ps --format '{{.Names}}' | grep -qx "$name"; then
            return 1
        fi
        sleep 1
    done
    return 1
}

_up_common() {
    local name=$1
    JEV_NAME[$name]="$RUN_ID-jev-$name"
    JEV_PORT[$name]=$_NEXT_PORT
    _NEXT_PORT=$((_NEXT_PORT + 1))
}

lcp_up() {
    local name=$1 gpus=$2 model=$3 ctx=$4 t0 port cname
    shift 4
    _up_common "$name"
    cname=${JEV_NAME[$name]}
    port=${JEV_PORT[$name]}
    if ! _model_present "$model"; then
        emit refused "$name" "model=$model" -- "the rig does not hold this path"
        return 1
    fi
    t0=$(date +%s)
    # shellcheck disable=SC2016
    # shellcheck disable=SC2086
    "$DOCKER" run -d --name "$cname" --gpus "$gpus" \
        -v "$RIG_HOME/models:/models:ro" $DATA_MOUNT \
        -p "$port:8080" "$LCP_IMG" --model "$model" -c "$ctx" -np 1 --jinja -lv 4 \
        --no-warmup --host 0.0.0.0 --port 8080 -a "$name" "$@" >/dev/null ||
        { emit refused "$name" "model=$model" -- "docker run failed"; return 1; }
    if ! _wait_health "$cname" "$port" /health; then
        emit refused "$name" "model=$model" -- "$("$DOCKER" logs "$cname" 2>&1 | grep -v '^$' | tail -2 | tr '\n\t' '  ' | cut -c1-300)"
        "$DOCKER" rm -f "$cname" >/dev/null 2>&1 || true
        return 1
    fi
    emit row "$name" LAUNCH "engine=lcp" "img=$LCP_IMG" "model=$model" "gpus=$gpus" "ctx=$ctx" \
        "load_s=$(( $(date +%s) - t0 ))" "extra=$(_tok "$(printf '%s' "$*" | tr ' ' '+')")"
}

vllm_up() {
    local name=$1 gpus=$2 model=$3 ctx=$4 t0 port cname
    shift 4
    _up_common "$name"
    cname=${JEV_NAME[$name]}
    port=${JEV_PORT[$name]}
    t0=$(date +%s)
    "$DOCKER" run -d --name "$cname" --runtime=nvidia --gpus "$gpus" \
        -v "$RIG_HOME/.cache/huggingface:/root/.cache/huggingface" \
        -v "$RIG_HOME/models:/models:ro" -e HF_HUB_OFFLINE=1 --ipc=host \
        -p "$port:8000" "$VLLM_IMG" "$model" --port 8000 --served-model-name "$name" \
        --dtype float16 --max-model-len "$ctx" --max-num-seqs 4 --max-logprobs 20 \
        --logprobs-mode raw_logprobs "$@" >/dev/null ||
        { emit refused "$name" "model=$model" -- "docker run failed"; return 1; }
    if ! _wait_health "$cname" "$port" /health; then
        emit refused "$name" "model=$model" -- "$("$DOCKER" logs "$cname" 2>&1 | grep -iE 'error|memory' | tail -2 | tr '\n\t' '  ' | cut -c1-300)"
        "$DOCKER" rm -f "$cname" >/dev/null 2>&1 || true
        return 1
    fi
    emit row "$name" LAUNCH "engine=vllm" "img=$VLLM_IMG" "model=$model" "gpus=$gpus" "ctx=$ctx" \
        "load_s=$(( $(date +%s) - t0 ))" "extra=$(_tok "$(printf '%s' "$*" | tr ' ' '+')")"
}

unit_config() {
    local name=$1 cname used
    cname=${JEV_NAME[$name]}
    used=$("$SSH" "$RUN_HOST" 'nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | paste -sd,' </dev/null)
    row "$name" CONFIG "card_used_mib=$(_tok "$used")" -- "$("$DOCKER" logs "$cname" 2>&1 |
        grep -E 'model buffer size|KV buffer size|compute buffer size|n_ctx_per_seq|KV cache size|Maximum concurrency|Using .*Kernel|attention backend' |
        sed 's/^[0-9.]* [A-Z] //' | tr '\n\t' '| ' | cut -c1-900)"
}

unit_down() {
    local name=$1 cname
    cname=${JEV_NAME[$name]:-}
    [ -n "$cname" ] || return 0
    "$DOCKER" rm -f "$cname" >/dev/null 2>&1 || true
    "$SSH" "$RUN_HOST" 'for i in 1 2 3 4 5 6 7 8 9 10; do sleep 1; done' </dev/null
}

all_down() {
    local n
    for n in "${!JEV_NAME[@]}"; do "$DOCKER" rm -f "${JEV_NAME[$n]}" >/dev/null 2>&1 || true; done
}

# The rig's home directory, read once: the container paths are the rig's
# ~/models and ~/.cache/huggingface, not the operator's.
RIG_HOME=""
#: `-v /data/models:/data:ro` where the rig has that store (srv1's HDD), else empty.
DATA_MOUNT=""
jev_images() {
    RIG_HOME=$("$SSH" "$RUN_HOST" 'printf %s "$HOME"' </dev/null) || { _fail "could not read \$HOME on $RUN_HOST" || true; exit 2; }
    if "$SSH" "$RUN_HOST" 'test -d /data/models' </dev/null; then DATA_MOUNT="-v /data/models:/data:ro"; fi
    local lcp_tag vllm_tag digest
    lcp_tag=${JEV_LCP_IMAGE:-llamacpp:b10644-L3-rpc}
    vllm_tag=${JEV_VLLM_IMAGE:-vllm/vllm-openai:v0.26.0}
    digest=$(image_digest "$lcp_tag") || { _fail "$lcp_tag resolves to no digest on $RUN_HOST" || true; exit 1; }
    export LCP_IMG="$digest"
    if [ "${JEV_NEED_VLLM:-0}" = 1 ]; then
        digest=$(image_digest "$vllm_tag") || { _fail "$vllm_tag resolves to no digest on $RUN_HOST" || true; exit 1; }
        export VLLM_IMG="$digest"
    fi
    emit stamp NOTE "lcp_image=$lcp_tag" "vllm_image=$vllm_tag" "rig_home=$RIG_HOME" "data_mount=$(_tok "${DATA_MOUNT:-none}")"
}

#!/usr/bin/env bash
# worker.sh LABEL — the worker's card, its rpc-server argv and image, as
# rpc-split filed worker-*.txt; appended to scratchpad/worker-steps.txt.
label=$1
out=/tmp/claude-1000/-home-adaramir-claude-mcgyvr-lab-open-issues/87def55d-87d9-44ae-ae4a-6fba1f6fdcc1/scratchpad/worker-steps.txt
ssh -o ConnectTimeout=15 -- srv2 "
echo \"## \$(date -u +%FT%T+00:00) $label\"
nvidia-smi --query-gpu=index,name,pci.bus_id,memory.total,memory.reserved,memory.used,memory.free,compute_cap,driver_version --format=csv,noheader
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader
docker ps --no-trunc --filter name=rpcw-pooled-slots --format '{{.Names}} {{.Image}} {{.Status}} {{.Command}}'
docker inspect rpcw-pooled-slots --format '{{.Image}}' 2>&1
grep MemAvailable /proc/meminfo
" >> "$out" 2>&1
tail -7 "$out"

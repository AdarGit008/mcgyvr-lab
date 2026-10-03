#!/usr/bin/env bash
# rigstate.sh HOST LABEL — what runs on a rig, read-only, one block.
host=$1
label=$2
ssh -o ConnectTimeout=15 -- "$host" "
echo \"## \$(date -u +%FT%TZ) $host $label\"
echo '# docker ps -a'
docker ps -a --no-trunc --format '{{.ID}} {{.Names}} {{.Image}} {{.Status}} {{.Command}}'
echo '# nvidia-smi --query-gpu'
nvidia-smi --query-gpu=index,name,pci.bus_id,memory.total,memory.reserved,memory.used,memory.free,compute_cap,driver_version --format=csv,noheader
echo '# nvidia-smi --query-compute-apps'
nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv,noheader
echo '# image llamacpp:b10644-L3-rpc'
docker image inspect llamacpp:b10644-L3-rpc --format '{{.Id}} created={{.Created}}'
echo '# lease'
cat ~/.mcgyvr/lease 2>/dev/null || echo none
grep MemAvailable /proc/meminfo
"

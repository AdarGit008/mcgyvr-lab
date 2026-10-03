#!/usr/bin/env bash
# sample per-card VRAM and pooled containers on both rigs every 5 s
out="$1"
while true; do
  ts=$(date +%T)
  for h in srv1 srv2; do
    v=$(timeout 10 ssh -o BatchMode=yes $h 'nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr "\n" ";"; echo -n " c="; docker ps --filter label=mcgyvr.pool=1 --format "{{.Label \"mcgyvr.pool.part\"}}:{{.Status}}" | tr "\n" ","' 2>&1)
    echo "$ts $h $v" >> "$out"
  done
  sleep 5
done

#!/usr/bin/env bash
# One timestamped line per change of our pooled containers / GPU memory on a rig.
h="$1"; n="${2:-600}"; last=""
for _ in $(seq 1 "$n"); do
  now=$(ssh -o BatchMode=yes "$h" 'docker ps --filter label=mcgyvr.pool=1 --format "{{.Label \"mcgyvr.part\"}}:{{.Status}}" | sed -E "s/Up [0-9]+ (seconds|minutes?)/Up/" | sort | tr "\n" " "; echo "| vram_used:" $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr "\n" " ")')
  [ "$now" != "$last" ] && { echo "$(date -u +%H:%M:%SZ) $h $now"; last="$now"; }
  sleep 2
done

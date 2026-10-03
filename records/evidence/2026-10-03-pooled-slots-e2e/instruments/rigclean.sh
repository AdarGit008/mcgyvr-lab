#!/usr/bin/env bash
# rigclean.sh HOST — remove what rigprep.sh and this run created on HOST, and
# nothing else: ~/mcgyvr-pool-tmp/product-slots, ~/mcgyvr-pool-tmp/e2e-slots
# (agent log, credentials for this run's hub, the worker's tensor cache) and
# ~/mcgyvr-pool-tmp/product-slots.bundle. Refuses while an agent from
# e2e-slots or a pooled container is still there. Images are handled by hand
# against the baseline (README).
set -euo pipefail
host=$1
ssh -o BatchMode=yes "$host" 'set -eu
cd ~/mcgyvr-pool-tmp
if [ -f e2e-slots/agent.pid ] && kill -0 "$(cat e2e-slots/agent.pid)" 2>/dev/null; then echo "agent still running"; exit 1; fi
[ -z "$(docker ps -aq --filter label=mcgyvr.pool=1)" ] || { echo "pooled containers still there"; exit 1; }
du -sh product-slots e2e-slots 2>/dev/null || true
rm -rf product-slots e2e-slots product-slots.bundle
ls -1 ~/mcgyvr-pool-tmp
'

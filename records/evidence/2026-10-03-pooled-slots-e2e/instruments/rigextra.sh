#!/usr/bin/env bash
# rigextra.sh HOST LABEL — read-only: images, agent/engine processes, the
# forwarded hub port, and the demo's folders on a rig (complements rigstate.sh).
host=$1
label=$2
ssh -o BatchMode=yes -o ConnectTimeout=15 -- "$host" "
echo \"## \$(date -u +%FT%TZ) $host $label (extra)\"
echo '# docker images -a'
docker images -a --format '{{.ID}} {{.Repository}}:{{.Tag}} {{.CreatedSince}} {{.Size}}' | sort
echo '# processes: agents, llama-server, ggml-rpc-server'
ps -eo pid,args | grep -E '[m]cgyvr rig|[l]lama-server|[g]gml-rpc-server' || echo none
echo '# listening on 18765/18766'
ss -ltn | grep -E ':1876[56] ' || echo none
echo '# ~/mcgyvr-pool-tmp'
ls -1 ~/mcgyvr-pool-tmp
echo '# product checkout'
git -C ~/mcgyvr-pool-tmp/product log --oneline -1
git -C ~/mcgyvr-pool-tmp/product status -sb | head -3
echo '# e2e dirs'
ls -1A ~/mcgyvr-pool-tmp/e2e ~/mcgyvr-pool-tmp/e2e/home 2>&1
ls -1A ~/mcgyvr-pool-tmp/e2e-slots 2>&1 | head -20
"

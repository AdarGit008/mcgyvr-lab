#!/usr/bin/env bash
# argcap.sh LABEL — read-only: the pooled containers on srv1 and srv2 as
# launched (name, part, image id, the engine argv from `mcgyvr-guard` on), and
# the head engine's own lines on slots, context and per-device buffers.
label=$1
echo "## $(date -u +%FT%TZ) $label"
for host in srv1 srv2; do
  ssh -o BatchMode=yes "$host" '
for c in $(docker ps -q --filter label=mcgyvr.pool=1); do
  docker inspect --format "{{.Name}} {{index .Config.Labels \"mcgyvr.pool.part\"}} {{.Image}} {{json .Config.Cmd}}" "$c" |
  python3 -c "
import json, sys
name, part, img, cmd = sys.stdin.read().split(\" \", 3)
argv = json.loads(cmd)
argv = argv[argv.index(\"mcgyvr-guard\"):] if \"mcgyvr-guard\" in argv else argv[-3:]
print(\"'"$host"'\", name, part, img, \" \".join(argv))
"
  if [ "$(docker inspect --format "{{index .Config.Labels \"mcgyvr.pool.part\"}}" "$c")" = head ]; then
    docker logs "$c" 2>&1 | grep -E "n_seq_max|n_ctx_seq|n_ctx  |kv_unified|KV buffer size|compute buffer size|offloaded .* layers|output layer|n_parallel|slots" | sed "s/^/'"$host"' head-log: /" | head -40
  fi
done'
done

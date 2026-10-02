#!/bin/bash
# Operator-only lock-down probes while a live session holds (scratch, never in a repo).
set -u
HEAD_LAN=192.168.1.144
WORKER_LAN=192.168.1.167
q() { ssh -o BatchMode=yes "$@"; }
name() { q "$1" "docker ps --filter label=mcgyvr.pool.part=$2 --format '{{.Names}}'"; }
WT=$(name srv2 tunnel); WK=$(name srv2 worker-0); HT=$(name srv1 tunnel); HD=$(name srv1 head)
echo "containers: worker-tunnel=$WT worker=$WK head-tunnel=$HT head=$HD"
W_IP=$(q srv2 "docker inspect -f '{{.NetworkSettings.IPAddress}}' $WT")
H_IP=$(q srv1 "docker inspect -f '{{.NetworkSettings.IPAddress}}' $HT")
API=$(q srv1 "docker port $HT 8080/tcp")
API_PORT=${API##*:}
echo "worker bridge ip=$W_IP head bridge ip=$H_IP head api published at: $API"
tcp() { # host, ip, port -> OPEN/CLOSED via bash /dev/tcp, 3 s
  q "$1" "timeout 3 bash -c '</dev/tcp/$2/$3' 2>/dev/null && echo OPEN || echo CLOSED"
}
echo "== P1 LAN (head rig) -> worker rig LAN:50052: $(tcp srv1 $WORKER_LAN 50052)"
echo "== P2 worker host -> worker container bridge ip:50052: $(tcp srv2 $W_IP 50052)"
echo "== P3 worker host -> tunnel address 10.211.7.2:50052: $(tcp srv2 10.211.7.2 50052)"
echo "== P4 head host -> worker tunnel address 10.211.7.2:50052 (outside tunnel): $(tcp srv1 10.211.7.2 50052)"
TAG=$(q srv2 "docker inspect -f '{{.Config.Image}}' $WT")
echo "== P5 another container on the worker's bridge -> $W_IP:50052: $(q srv2 "docker run --rm --entrypoint sh $TAG -c 'nc -w 3 $W_IP 50052 </dev/null >/dev/null 2>&1 && echo OPEN || echo CLOSED'")"
echo "== P6 worker rig (LAN) -> head rig LAN:$API_PORT (head api): $(tcp srv2 $HEAD_LAN $API_PORT)"
echo "== P7 worker rig (LAN) -> head rig LAN:8080: $(tcp srv2 $HEAD_LAN 8080)"
echo "== P8 head host loopback -> $API /health: $(q srv1 "curl -s -m 3 http://$API/health")"
echo "== P9 head host listening sockets on the api port:"; q srv1 "ss -lnt | grep ':$API_PORT ' || true"
echo "== P10 worker host listening on 50052 (expect none):"; q srv2 "ss -lnt | grep ':50052 ' || echo none"
echo "== P11 worker host udp listeners for the tunnel port:"; q srv2 "ss -lnu | grep ':51820 ' || echo none"
for pair in "srv2 $WK" "srv1 $HD"; do
  set -- $pair
  echo "== P12 $1 $2 inside:"
  q "$1" "docker exec $2 sh -c 'id; grep -E \"^(CapInh|CapPrm|CapEff|CapBnd|CapAmb|NoNewPrivs|Seccomp):\" /proc/1/status; touch /probe 2>&1 | head -1; ls /sys/class/net'"
  echo "== P13 $1 $2 config:"
  q "$1" "docker inspect -f 'User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} CapDrop={{.HostConfig.CapDrop}} CapAdd={{.HostConfig.CapAdd}} Privileged={{.HostConfig.Privileged}} NetworkMode={{.HostConfig.NetworkMode}} PidMode={{.HostConfig.PidMode}} IpcMode={{.HostConfig.IpcMode}} Memory={{.HostConfig.Memory}} MemorySwap={{.HostConfig.MemorySwap}} PidsLimit={{.HostConfig.PidsLimit}} Ports={{.HostConfig.PortBindings}} Mounts={{range .Mounts}}{{.Source}}:{{.Destination}}:rw={{.RW}} {{end}} SecOpt={{range .HostConfig.SecurityOpt}}{{printf \"%.40s\" .}} {{end}}' $2"
done
for pair in "srv2 $WT" "srv1 $HT"; do
  set -- $pair
  echo "== P14 $1 tunnel $2 config:"
  q "$1" "docker inspect -f 'User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} CapDrop={{.HostConfig.CapDrop}} CapAdd={{.HostConfig.CapAdd}} Privileged={{.HostConfig.Privileged}} NetworkMode={{.HostConfig.NetworkMode}} Ports={{.HostConfig.PortBindings}} Mounts={{len .Mounts}}' $2"
  echo "== P15 $1 tunnel ruleset:"; q "$1" "docker exec $2 nft list ruleset"
  echo "== P16 $1 wg (public parts only):"; q "$1" "docker exec $2 wg show wg0 | grep -v 'private key'"
  echo "== P17 $1 does the private key appear anywhere outside the tunnel (logs, inspect)?"
  q "$1" "K=\$(docker exec $2 wg show wg0 private-key); { docker logs $2 2>&1; docker inspect $2; } | grep -cF \"\$K\" || true"
done
echo "== P18 host kernel unchanged (wireguard module loaded?):"
for h in srv1 srv2; do echo "$h: $(q $h 'lsmod | grep -c ^wireguard || true')"; done

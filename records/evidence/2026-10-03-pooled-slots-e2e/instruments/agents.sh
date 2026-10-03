#!/usr/bin/env bash
# agents.sh up | down — the rig agents under test (mcgyvr rig-head-slots @
# abccb902), as tools/demo/demo-up starts them, in folders of their own:
#   srv1 (head-rig, usr1): ~/mcgyvr-pool-tmp/e2e-slots, through agenttrace.py
#   srv2 (worker-rig, usr2): ~/mcgyvr-pool-tmp/e2e-slots, plain `mcgyvr rig`
#   here (vps-a usr3, vps-b usr4): $STATE/vps-*, no card, lending the worker role
#     only so that usr3 and usr4 give to the pool (the hub's access rule); the
#     planner cannot place a layer on a rig with no card.
# One `ssh -R` per rig gives its loopback :PORT this host's hub.
# The first `up` joins with the rig's token (over ssh's stdin into a 0600 file
# read once); later ones `rig run` from the saved credentials.
# down: SIGTERM each agent (it stops its sessions), remove any pooled container
# left, close the tunnels.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export STATE="${STATE:-$HOME/.local/state/mcgyvr-demo-slots-e2e}"
PORT="${PORT:-18766}"
export HUB="http://127.0.0.1:$PORT"
REMOTE='mcgyvr-pool-tmp/e2e-slots'
LOCAL_MCGYVR=/home/adaramir/claude/mcgyvr-product-slots/.venv/bin/mcgyvr
say() { printf '[agents.sh %s] %s\n' "$(date -u +%T)" "$*"; }
alive() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }

remote_agent() {  # host rig tracer(0|1)
  local host=$1 rig=$2 trace=$3 verb
  if ! ssh -o BatchMode=yes "$host" "test -f ~/$REMOTE/home/rig-credentials.json"; then
    python3 "$HERE/ctl.py" token "$rig" | ssh -o BatchMode=yes "$host" "umask 077; cat > ~/$REMOTE/join-token"
    verb="rig join http://127.0.0.1:$PORT --token -"
  else
    verb="rig run"
  fi
  if [ "$trace" = 1 ]; then
    scp -q "$HERE/agenttrace.py" "$host:$REMOTE/agenttrace.py"
    cmd="../product-slots/.venv/bin/python ./agenttrace.py $verb"
  else
    cmd="../product-slots/.venv/bin/mcgyvr $verb"
  fi
  ssh -o BatchMode=yes "$host" "set -eu; cd ~/$REMOTE
    if [ -f agent.pid ] && kill -0 \$(cat agent.pid) 2>/dev/null; then echo 'agent already running'; exit 0; fi
    in=/dev/null; [ -f join-token ] && in=join-token
    echo \"### \$(date -u +%FT%TZ) $cmd\" >> agent.log
    MCGYVR_HOME=\$PWD/home MCGYVR_DATA=\$PWD/data AGENTTRACE_FILE=\$PWD/agenttrace.jsonl \
      setsid nohup $cmd <\"\$in\" >>agent.log 2>&1 &
    echo \$! > agent.pid
    sleep 3
    rm -f join-token
    kill -0 \$(cat agent.pid) || { tail -5 agent.log; exit 1; }"
  say "agent on $host started ($verb)"
}

local_agent() {  # rig listen_port
  local rig=$1 port=$2 dir="$STATE/$1" verb
  mkdir -p "$dir/home" "$dir/data"
  chmod 700 "$dir" "$dir/home"
  alive "$dir/agent.pid" && { say "agent $rig already running"; return 0; }
  [ -f "$dir/home/rig-sharing.json" ] || cat >"$dir/home/rig-sharing.json" <<EOF
{"enabled": true, "roles": ["worker"], "image": "llamacpp:b10644-L3-rpc", "cards": null,
 "max_ram_mb": null, "models_dir": null, "endpoints": [], "listen_port": $port,
 "cache": false, "cache_max_mb": 16384, "head_binary": "/app/llama-server",
 "worker_binary": "/app/ggml-rpc-server"}
EOF
  if [ -f "$dir/home/rig-credentials.json" ]; then
    verb="rig run"
    in=/dev/null
  else
    (umask 077; python3 "$HERE/ctl.py" token "$rig" >"$dir/join-token")
    verb="rig join http://127.0.0.1:$PORT --token -"
    in="$dir/join-token"
  fi
  echo "### $(date -u +%FT%TZ) $verb" >>"$dir/agent.log"
  MCGYVR_HOME="$dir/home" MCGYVR_DATA="$dir/data" \
    setsid nohup "$LOCAL_MCGYVR" $verb <"$in" >>"$dir/agent.log" 2>&1 &
  echo $! >"$dir/agent.pid"
  sleep 3
  rm -f "$dir/join-token"
  alive "$dir/agent.pid" || { tail -5 "$dir/agent.log"; exit 1; }
  say "agent $rig started here ($verb)"
}

case "${1:-}" in
up)
  for host in srv1 srv2; do
    pidf="$STATE/tunnel-$host.pid"
    if alive "$pidf"; then say "tunnel to $host already up"; continue; fi
    setsid nohup ssh -N -o BatchMode=yes -o ExitOnForwardFailure=yes \
      -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
      -R "127.0.0.1:$PORT:127.0.0.1:$PORT" "$host" >>"$STATE/tunnel-$host.log" 2>&1 </dev/null &
    echo $! >"$pidf"
    sleep 2
    alive "$pidf" || { say "tunnel to $host failed"; cat "$STATE/tunnel-$host.log"; exit 1; }
    say "tunnel to $host up (pid $(cat "$pidf"))"
  done
  remote_agent srv1 head-rig 1
  remote_agent srv2 worker-rig 0
  local_agent vps-a 51831
  local_agent vps-b 51832
  python3 "$HERE/ctl.py" wait-online 120
  ;;
down)
  for host in srv1 srv2; do
    ssh -o BatchMode=yes "$host" "cd ~/$REMOTE 2>/dev/null || exit 0
      if [ -f agent.pid ]; then
        p=\$(cat agent.pid)
        if kill -0 \$p 2>/dev/null; then
          kill -TERM \$p
          for i in \$(seq 1 150); do kill -0 \$p 2>/dev/null || break; sleep 1; done
          kill -0 \$p 2>/dev/null && { kill -KILL \$p; echo 'agent killed hard'; }
        fi
        rm -f agent.pid
      fi
      left=\$(docker ps -aq --filter label=mcgyvr.pool=1)
      [ -n \"\$left\" ] && { echo \"removing leftover pooled containers: \$left\"; docker rm -f --volumes \$left >/dev/null; }
      rm -f join-token
      exit 0" && say "agent on $host stopped"
  done
  for rig in vps-a vps-b; do
    f="$STATE/$rig/agent.pid"
    if alive "$f"; then
      p=$(cat "$f")
      kill -TERM "$p"
      for _ in $(seq 1 30); do kill -0 "$p" 2>/dev/null || break; sleep 1; done
      kill -0 "$p" 2>/dev/null && kill -KILL "$p"
    fi
    rm -f "$f"
    say "agent $rig stopped"
  done
  for host in srv1 srv2; do
    f="$STATE/tunnel-$host.pid"
    if alive "$f"; then kill -TERM "$(cat "$f")"; fi
    rm -f "$f"
    say "tunnel to $host closed"
  done
  ;;
*)
  echo "usage: agents.sh up | down" >&2
  exit 2
  ;;
esac

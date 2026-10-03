#!/usr/bin/env bash
# hub.sh start TARGET_SLOTS CTX_PER_SLOT WAIT_SLOT_S | stop
# The hub under test (mcgyvr-hub pool-head-slots @ 76cd212, a detached worktree)
# on this host's loopback, as tools/demo/demo-up starts it, through hubtrace.py.
#   start: MCGYVR_HUB_PLANNER_TARGET_SLOTS, MCGYVR_HUB_PLANNER_DEFAULT_CTX and
#          MCGYVR_HUB_CHAT_WAIT_SLOT_S as given; every other setting the hub's
#          default. Bootstraps users and rigs once (ctl.py).
#   stop:  stop every running session through the API, wait until neither rig
#          has a pooled container, then stop the hub (SIGTERM).
# State (database, secrets, logs, traces) lives in $STATE, outside the repo.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export STATE="${STATE:-$HOME/.local/state/mcgyvr-demo-slots-e2e}"
HUB_REPO="${HUB_REPO:-/home/adaramir/claude/mcgyvr-hub-e2e}"
PORT="${PORT:-18766}"
export HUB="http://127.0.0.1:$PORT"
say() { printf '[hub.sh %s] %s\n' "$(date -u +%T)" "$*"; }
alive() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }
mkdir -p "$STATE"
chmod 700 "$STATE"

case "${1:-}" in
start)
  target=$2 ctx=$3 wait=$4
  alive "$STATE/hub.pid" && { say "hub already running"; exit 1; }
  echo "### $(date -u +%FT%T.%3NZ) start target_slots=$target default_ctx=$ctx chat_wait_slot_s=$wait" >>"$STATE/hub.log"
  (
    cd "$HUB_REPO"
    MCGYVR_HUB_PLANNER_TARGET_SLOTS="$target" MCGYVR_HUB_PLANNER_DEFAULT_CTX="$ctx" \
      MCGYVR_HUB_CHAT_WAIT_SLOT_S="$wait" HUBTRACE_FILE="$STATE/hubtrace.jsonl" \
      setsid nohup "$HUB_REPO/.venv/bin/python" "$HERE/hubtrace.py" serve \
      --host 127.0.0.1 --port "$PORT" --db "$STATE/hub.db" >>"$STATE/hub.log" 2>&1 </dev/null &
    echo $! >"$STATE/hub.pid"
  )
  echo "$HUB" >"$STATE/hub.url"
  for _ in $(seq 1 60); do
    curl -fsS "$HUB/api/v1/health" >/dev/null 2>&1 && break
    sleep 0.5
  done
  curl -fsS "$HUB/api/v1/health" >/dev/null || { say "hub did not come up"; tail -20 "$STATE/hub.log"; exit 1; }
  say "hub up on 127.0.0.1:$PORT pid $(cat "$STATE/hub.pid") target_slots=$target ctx=$ctx wait_slot=$wait"
  python3 "$HERE/ctl.py" bootstrap
  ;;
stop)
  if alive "$STATE/hub.pid"; then
    python3 "$HERE/ctl.py" stop-all || true
    for _ in $(seq 1 90); do
      n=0
      for h in srv1 srv2; do
        c=$(ssh -o BatchMode=yes "$h" 'docker ps -aq --filter label=mcgyvr.pool=1 | wc -l')
        n=$((n + c))
      done
      [ "$n" = 0 ] && break
      sleep 2
    done
    say "pooled containers left on the rigs: $n"
    p=$(cat "$STATE/hub.pid")
    kill -TERM "$p"
    for _ in $(seq 1 20); do kill -0 "$p" 2>/dev/null || break; sleep 1; done
    kill -0 "$p" 2>/dev/null && { kill -KILL "$p"; say "hub killed hard"; }
    rm -f "$STATE/hub.pid"
    echo "### $(date -u +%FT%T.%3NZ) stopped" >>"$STATE/hub.log"
    say "hub stopped"
  else
    say "no hub running"
  fi
  ;;
*)
  echo "usage: hub.sh start TARGET_SLOTS CTX_PER_SLOT WAIT_SLOT_S | stop" >&2
  exit 2
  ;;
esac

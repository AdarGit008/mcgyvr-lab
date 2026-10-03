#!/usr/bin/env bash
# Item 4a: stop the worker rig's agent (SIGTERM) mid-answer of a streamed 32B
# request, send a second request while the unit is held, restart the agent as
# soon as the old one has exited, and log every step with UTC timestamps.
#   fleet_change.sh <outdir> [restart_delay_s]
set -u
out="$1"; delay="${2:-0}"; pre="${3:-}"; M=Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf
# pre: a shell snippet run on srv2 while its agent is away
here="$(cd "$(dirname "$0")" && pwd)"
t() { date -u +%T.%3N; }
cd "$here"
python3 chat.py head-owner "$M" --stream --max 400 --trace > "$out/A-stream.txt" 2>&1 &
A=$!
sleep 6
echo "$(t) SIGTERM worker agent on srv2"
ssh -o BatchMode=yes srv2 'kill -TERM $(cat ~/mcgyvr-pool-tmp/e2e/agent.pid)'
sleep 3
python3 chat.py head-owner "$M" --max 64 > "$out/B-during-hold.txt" 2>&1 &
B=$!
# wait for the old agent to exit
for i in $(seq 1 300); do
  ssh -o BatchMode=yes srv2 'kill -0 $(cat ~/mcgyvr-pool-tmp/e2e/agent.pid) 2>/dev/null' || break
  sleep 0.5
done
echo "$(t) old worker agent has exited"
ssh -o BatchMode=yes srv2 'docker ps --filter label=mcgyvr.pool=1 --format "{{.Names}}"' | sed "s/^/$(t) srv2 container left: /"
[ -n "$pre" ] && { echo "$(t) on srv2: $pre"; ssh -n -o BatchMode=yes srv2 "$pre"; }
sleep "$delay"
echo "$(t) starting worker agent again (rig run)"
ssh -n -o BatchMode=yes srv2 'set -eu; cd ~/mcgyvr-pool-tmp/e2e
  MCGYVR_HOME=$PWD/home MCGYVR_DATA=$PWD/data setsid nohup ../product/.venv/bin/mcgyvr rig run </dev/null >>agent.log 2>&1 &
  echo $! > agent.pid'
wait $A; echo "$(t) request A finished"
wait $B; echo "$(t) request B finished"

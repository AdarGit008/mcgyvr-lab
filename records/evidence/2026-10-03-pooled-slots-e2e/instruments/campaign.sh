#!/usr/bin/env bash
# campaign.sh — the throughput invocations, arms interleaved:
#   rounds a b c, each T4 T1 T4N T1N (target slots 4, 1, 4, 1), so every arm
#   has six invocations and no two of one arm run back to back.
# One invocation = a fresh hub (hub.sh stop; hub.sh start TARGET 10240 900),
# so a fresh session: the warm-up (workload draw 0, discarded), the launched
# argv (argcap.sh), then cell c4 (draws 4..7, one per user) and cell c8
# (draws 4..11, two per user), one load.py run per cell.
# chat_wait_slot_s is 900 s here so every request of a cell is served; the
# 30 s default is exercised in the queue cells (README).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
EV="$(cd "$HERE/.." && pwd)"
export STATE="${STATE:-$HOME/.local/state/mcgyvr-demo-slots-e2e}"
log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$EV/campaign.log"; }
one() {  # label target
  local label=$1 target=$2
  log "BEGIN $label target_slots=$target"
  "$HERE/hub.sh" stop >>"$EV/campaign.log" 2>&1
  "$HERE/hub.sh" start "$target" 10240 900 >>"$EV/campaign.log" 2>&1 || { log "FAIL $label hub"; return 1; }
  python3 "$HERE/ctl.py" wait-online 180 >>"$EV/campaign.log" 2>&1 || { log "FAIL $label online"; return 1; }
  timeout 1200 python3 "$HERE/load.py" warm "$label" "$label-warm" >"$EV/rows/$label-warm.jsonl"
  log "warm done $label"
  "$HERE/argcap.sh" "$label" >"$EV/args/$label.txt" 2>&1
  timeout 1800 python3 "$HERE/load.py" c4 "$label" "$label-c4" >"$EV/rows/$label-c4.jsonl"
  log "c4 done $label"
  timeout 2400 python3 "$HERE/load.py" c8 "$label" "$label-c8" >"$EV/rows/$label-c8.jsonl"
  log "END $label"
}
for r in a b c; do
  one "T4-$r" 4
  one "T1-$r" 1
  one "T4N-$r" 4
  one "T1N-$r" 1
done
"$HERE/hub.sh" stop >>"$EV/campaign.log" 2>&1
log "CAMPAIGN DONE"

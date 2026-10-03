#!/usr/bin/env bash
# argcap.sh — while the chain runs, file each head container's argv once
# (docker inspect on srv1, read-only).
out=/tmp/claude-1000/-home-adaramir-claude-mcgyvr-lab-open-issues/87def55d-87d9-44ae-ae4a-6fba1f6fdcc1/scratchpad/head-args-inspected.txt
seen=""
while pgrep -f "[c]hain.sh" >/dev/null; do
    got=$(ssh -o ConnectTimeout=10 srv1 'for c in $(docker ps --filter name=pooled-slots --format "{{.Names}}"); do echo "$c|$(docker inspect $c --format "{{.Image}}")|$(docker inspect $c --format "{{json .Config.Cmd}}")"; done' 2>/dev/null)
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        cmd=${line#*|}
        case "$seen" in *"$cmd"*) continue ;; esac
        seen="$seen
$cmd"
        echo "## $(date -u +%FT%TZ) ${line%%|*}" >>"$out"
        echo "${cmd}" >>"$out"
    done <<<"$got"
    sleep 15
done

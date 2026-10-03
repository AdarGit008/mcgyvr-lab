# on a rig: sample the pooled tunnel's cgroup memory (current, and the anon/sock/file split) every 0.5 s for $1 s
end=$(( $(date +%s) + $1 ))
while [ "$(date +%s)" -lt "$end" ]; do
  for id in $(docker ps -q --no-trunc --filter label=mcgyvr.pool.part=tunnel); do
    d=/sys/fs/cgroup/system.slice/docker-$id.scope
    [ -r $d/memory.current ] || continue
    cur=$(cat $d/memory.current); peak=$(cat $d/memory.peak 2>/dev/null)
    st=$(awk '$1=="anon"||$1=="sock"||$1=="file"||$1=="kernel"||$1=="shmem"{printf "%s=%d ",$1,$2/1048576}' $d/memory.stat)
    oom=$(awk '$1=="oom_kill"{print $2}' $d/memory.events)
    echo "$(date +%T.%N | cut -c1-12) cur=$((cur/1048576)) peak=$((peak/1048576)) $st oom_kill=$oom"
  done
  sleep 0.5
done

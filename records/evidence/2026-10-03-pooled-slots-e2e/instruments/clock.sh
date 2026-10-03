#!/usr/bin/env bash
# clock.sh HOST — HOST's time.time() minus this host's, over one ssh session
# (20 ping-pongs with a remote python loop; the shortest round trip is the
# estimate, good to half that round trip).
host=$1
python3 - "$host" <<'EOF'
import shlex, subprocess, sys, time
host = sys.argv[1]
loop = "import sys,time; [print(f'{time.time():.6f}', flush=True) for _ in sys.stdin]"
p = subprocess.Popen(["ssh", "-o", "BatchMode=yes", host, "python3 -u -c " + shlex.quote(loop)],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
best = None
for _ in range(20):
    a = time.time(); p.stdin.write("x\n"); p.stdin.flush()
    r = float(p.stdout.readline()); b = time.time()
    if best is None or b - a < best[0]:
        best = (b - a, r - (a + b) / 2)
p.stdin.close(); p.wait()
print(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {host} rtt={best[0]*1000:.1f}ms offset={best[1]*1000:+.1f}ms")
EOF

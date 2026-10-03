import statistics
import sys
from pathlib import Path

env = Path(sys.argv[1])
by: dict[tuple[str, str], list[float]] = {}
for name in ("round-a.tsv", "round-b.tsv", "round-c.tsv"):
    for line in (env / name).read_text().splitlines():
        p = line.split("\t")
        if len(p) < 4 or p[2] != "REQ":
            continue
        arm = p[1].split()[0].rsplit("-", 1)[0]
        kv = dict(x.split("=", 1) for x in p[3:] if "=" in x)
        if kv["tok"] == "unread" or int(kv["gen"]) < 2:
            continue
        t = (float(kv["end"]) - float(kv["tok"])) / (int(kv["gen"]) - 1) * 1000
        by.setdefault((arm, kv["n"]), []).append(t)
for arm in ("H1", "S1", "H2", "S2", "H4", "S4", "D6OUT1", "D4GAP", "D4SEQ", "D5STAG"):
    print(arm, " ".join(f"C={c}:{statistics.median(by[(arm, c)]):.0f}ms(n={len(by[(arm, c)])})"
                        for c in ("1", "2", "4") if (arm, c) in by))

import sys, os
sys.path.insert(0, os.path.expanduser("~/mcgyvr-pool-tmp/product/src"))
from mcgyvr.serving import ggufscan as g
import struct
for path in sys.argv[1:]:
    with open(path, "rb") as f:
        r = g.R(f); assert f.read(4) == b"GGUF"
        r.u32(); nt = r.u64(); nkv = r.u64()
        kv = {}
        for _ in range(nkv):
            k = r.st(); t = r.u32(); kv[k] = r.val(t)
        ts = []
        for _ in range(nt):
            name = r.st(); nd = r.u32(); dims = [r.u64() for _ in range(nd)]; tt = r.u32(); r.u64()
            n = 1
            for d in dims: n *= d
            be, bb = g.T[tt]; ts.append((name, dims, tt, n // be * bb))
    size = os.path.getsize(path)
    blk = {}
    other = {}
    for name, dims, tt, b in ts:
        if name.startswith("blk."):
            i = int(name.split(".")[1]); blk[i] = blk.get(i, 0) + b
        else:
            other[name] = (dims, tt, b)
    arch = kv.get("general.architecture")
    print(os.path.basename(path), "size", size, "tensors", sum(t[3] for t in ts), "header", size - sum(t[3] for t in ts))
    print(" vocab", len(kv.get("tokenizer.ggml.tokens", [])), "n_embd", kv.get(f"{arch}.embedding_length"), "n_ff", kv.get(f"{arch}.feed_forward_length"), kv.get(f"{arch}.expert_feed_forward_length"), "n_head", kv.get(f"{arch}.attention.head_count"))
    for k, v in other.items(): print(" ", k, v)
    vals = [blk[i] for i in sorted(blk)]
    print(" blocks", len(vals), "min", min(vals), "max", max(vals), "sum", sum(vals))

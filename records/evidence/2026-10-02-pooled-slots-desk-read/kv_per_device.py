"""Per-device KV cells for the pooled head's launch, from llama.cpp b10644 source.

A desk calculation, not a measurement. It re-implements, line for line, three
pieces of llama.cpp at commit d7a2074112d27649303fa107eb8c94db1ee435f3:

* the layer-to-device split for -sm layer with -ts (src/llama-model.cpp:1418-1474);
* n_ctx / n_ctx_seq with and without --kv-unified (src/llama-context.cpp:287-304);
* one K and one V tensor per layer of [n_embd_gqa, kv_size = n_ctx_seq, n_stream]
  on that layer's device (src/llama-kv-cache.cpp:83, 211-233;
  src/llama-model.cpp:2577-2593).

The bytes per token come from the product's own estimate in the rig hello
(`kv_bytes_per_token`, recorded in lab PR #42's run3.jsonl for
Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf, 64 layers), so they carry that
estimate's assumptions; the cell counts do not.

Run: python3 kv_per_device.py
"""

from __future__ import annotations

import bisect

N_LAYER = 64  # hello: n_layers for Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf
KV_BYTES_PER_TOKEN = 139264  # hello: kv_bytes_per_token (all layers, K+V)
NGL = 999  # head-args-3.txt: -ngl 999
DEVICES = ("CUDA0", "CUDA1", "RPC0")  # head-args-3.txt: -dev CUDA0,CUDA1,RPC0
TS = (27, 26, 12)  # head-args-3.txt: -ts 27,26,12
C = 12288  # head-args-3.txt: -c 12288


def pad(x: int, n: int) -> int:
    """GGML_PAD: round x up to a multiple of n."""
    return (x + n - 1) // n * n


def layer_devices() -> list[str]:
    """src/llama-model.cpp:1436-1474, the -ts branch.

    Index N_LAYER is the output layer (:1474).
    """
    total = float(sum(TS))
    splits, acc = [], 0.0
    for share in TS:
        acc += share
        splits.append(acc / total)
    n_layer_all = N_LAYER
    i_gpu_start = max(n_layer_all + 1 - NGL, 0)
    act_gpu_layers = min(NGL, n_layer_all + 1)
    out = []
    for il in range(n_layer_all + 1):
        if il < i_gpu_start or (il - i_gpu_start) >= act_gpu_layers:
            out.append("CPU")
            continue
        frac = float(il - i_gpu_start) / act_gpu_layers
        out.append(DEVICES[bisect.bisect_right(splits, frac)])
    return out


def ctx(n_ctx: int, n_seq_max: int, unified: bool) -> tuple[int, int, int]:
    """src/llama-context.cpp:288-304: (n_ctx, n_ctx_seq, n_stream)."""
    n_ctx = pad(n_ctx, 256)
    if unified:
        return n_ctx, n_ctx, 1
    n_ctx_seq = pad(n_ctx // n_seq_max, 256)
    return n_ctx_seq * n_seq_max, n_ctx_seq, n_seq_max


def main() -> None:
    all_devs = layer_devices()
    devs, output_dev = all_devs[:N_LAYER], all_devs[N_LAYER]
    per_layer_token = KV_BYTES_PER_TOKEN // N_LAYER
    counts = {d: devs.count(d) for d in (*DEVICES, "CPU")}
    ts = ",".join(map(str, TS))
    print(f"layers per device (-ngl {NGL} -ts {ts}, {N_LAYER} layers):")
    for d, k in counts.items():
        if k:
            first, last = devs.index(d), len(devs) - 1 - devs[::-1].index(d)
            print(f"  {d}: {k} layers (il {first}..{last})")
    print(f"  output layer (il {N_LAYER}): {output_dev}")
    print(f"KV bytes per layer per token (hello estimate / n_layer): {per_layer_token}")
    print()
    hdr = f"{'case':<34}{'N':>3}{'n_ctx':>8}{'ctx/slot':>10}{'streams':>9}"
    hdr += "".join(f"{d + ' MiB':>12}" for d in DEVICES)
    print(hdr)
    cases = []
    for n in (1, 2, 3, 4, 5):
        cases.append((f"-c {C} -np {n}", n, C, False))
    for n in (2, 4):
        cases.append((f"-c {C} -np {n} -kvu", n, C, True))
    for n in (2, 4):
        cases.append((f"-c {n * C} -np {n} (same ctx/slot)", n, n * C, False))
    for name, n, c, unified in cases:
        n_ctx, n_ctx_seq, n_stream = ctx(c, n, unified)
        cells = n_ctx_seq * n_stream
        row = f"{name:<34}{n:>3}{n_ctx:>8}{n_ctx_seq:>10}{n_stream:>9}"
        for d in DEVICES:
            row += f"{counts[d] * per_layer_token * cells / 2**20:>12.1f}"
        print(row)
    print()
    print(
        "ctx/slot under -kvu is the shared pool every slot draws from,"
        " not a per-slot reservation."
    )


if __name__ == "__main__":
    main()

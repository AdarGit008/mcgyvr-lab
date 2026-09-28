# srv1-multi-gpu: top takeaways (2× RTX 3060 12 GB, PCIe gen3 x8/x8, i5-9600K)

E = /home/adaramir/claude/mcgyvr/records/evidence/2026-09-27-srv1-multi-gpu. Figures are tpot_ms_p50 at n=1 unless marked.
Read by three reviewers (hardware, engine, model profile); spot-checked against the TSVs.

## Hardware
1. **Each all-reduce costs about 0.06 ms regardless of size.** Latency stays flat from 4 KiB to 32 KiB and then grows with size: 0.06 ms at 4 KiB, 0.339 ms at 1 MiB, 17.4 ms at 64 MiB (3.59 GiB/s). Rows: E/nccl.tsv 'nccl-base bytes=…'.
2. **ReBAR and P2P did not change NCCL.** With BAR1 at 16 GiB (E/rebar.tsv) and with P2P granted (E/p2p.tsv PEERGATE `copy_verified=True`), NCCL still went via `SHM/direct/direct`. The 64 MiB all-reduce took 17.05 ms with P2P off and 16.83 ms with it on (E/p2p.tsv 'p2p-link-off/on'). The path between the cards is `PHB`, through the CPU.
3. **A direct copy between the cards doubled with P2P:** 2.95 GiB/s before (E/link.tsv 'link-p2p-on' PEER) and 6.11 GiB/s after (E/p2p.tsv 'p2p-link-on' PEER).
4. **PCIe gen2 measured slower than gen1.** Host-to-card copy: 6.06 GiB/s at gen3, 0.24 at gen2, 1.23 at gen1. The 64 MiB all-reduce: 17.95 ms at gen3, 408.96 at gen2, 120.52 at gen1 (E/pcie.tsv 'pcie-gen*'). Link speed alone does not predict gen2 below gen1 (inference: the link is unstable at 5 GT/s). At idle the links read 2.5 GT/s even when targeting gen3; that is power saving.
5. **The host is tight under vLLM TP-2.** At n=16 one core runs at 99%, the least free RAM was 283 MiB, and nothing swapped. Under DP-2 the hottest core is at 20% (E/p2p.tsv 'p7-tp2' and 'p7-dp2' n=16).

## Engine
6. **Two cards cut per-token latency only through tensor parallelism, and only with CUDA graphs.**
   - vLLM 7B AWQ: one card 14.5, TP-2 8.2 (1.77×); PP-2 14.5 and DP-2 14.4 (E/p2p.tsv 'p7-*', E/vllm.tsv 'v7b-*').
   - With `--enforce-eager`, TP-2 goes to 23.3 against 19.3 on one card (E/vknobs.tsv 'k7-*-eager').
7. **DP-2 gives more total throughput under concurrency.** At n=32, 7B: DP-2 585 tok/s at 26.4 ms, TP-2 428 tok/s at 41.8 ms. 1.5B: DP-2 1623, TP-2 1112 (E/vllm.tsv).
8. **Custom all-reduce, now allowed by P2P, only helps under load.** At n=16, TP-2: 16.2 ms and 655 tok/s with it, 19.2 / 595 without it, 18.4 / 603 with P2P off. At n=1: 8.2 against 8.6 (E/p2p.tsv). The launch where vLLM ran its own P2P test disabled it ('p7-tp2-check' LOG), although the step's own peer copy verified; the cause is not measured yet.
9. **TP-2 holds 3.65× the KV cache of one card:** 263k tokens against 72k; fp8 KV gives 526k (E/vsched.tsv 's7-tp2-fp8kv'). A 54.6k-token prefill takes 24.0 s on one card, 16.1 s with TP-2 and 13.3 s with PP-2 (E/vctx.tsv).
10. **llama.cpp tensor split is faster at n=1 but not under load.** 14B at n=1: one card 29.8, layer split 29.7, tensor split 18.2. At n=16: tensor 86.7, layer 83.8. `GGML_CUDA_P2P=1` moved tpot by at most 0.2 ms (E/lcp.tsv, E/p2p.tsv 'pl14-*').

## Model profile
11. **For dense models, the rule tp ≈ g0/2 + 2L×0.033 ms predicts tensor-split tpot within 0.5 ms from 1.5B to 32B.** The speed-up grows with size: 1.13× at 1.5B, 1.30× at 4B, 1.56× at 8B, 1.64× at 14B, 1.75× at 32B (E/ladder.tsv, E/lcp.tsv). Layer counts other than 4B/8B are inferred.
12. **MoE tpot does not follow bytes.** Within one qwen35moe shape, bytes grow 1.84× (10,988 to 20,186 MiB) while tensor-split tpot stays between 9.6 and 11.4. The dense rule predicts MoE 0.5–1.9 ms too low. At equal bytes, Ling runs 6.5 against Qwen3-8B's 16.9 at n=1, and 68.0 against 64.2 at n=16 (E/ladder.tsv).
13. **Some models load only across both cards:** 32B, Qwen3.6-35B-A3B IQ3, Coder-30B Q4, KAT Q4. Putting experts on the CPU instead costs 1.4–2.5× (E/offload.tsv 'o30-g0-cm24' 24.6 against 9.8 on two cards). Context length barely moves n=1 tpot: 14B on one card is 30.0 at 32k (E/lctx.tsv).

## Not measured / refused
- vLLM 14B and 32B AWQ: the weights are not on srv1.
- qmoe and DeepSeek-Lite TP-2: the vLLM engine failed to initialize.
- llama.cpp row split: no split buffers.
- Tensor split for deepseek2, bailingmoe3 and nemotron_h_moe: not implemented.
- Why NCCL picks SHM: no NCCL line gives a reason (inference: its default P2P level excludes PHB). Not tested with `NCCL_P2P_LEVEL=SYS`.
- Why vLLM's P2P test failed: not measured.

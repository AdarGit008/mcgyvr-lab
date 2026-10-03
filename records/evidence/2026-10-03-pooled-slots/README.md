# Pooled-head slots: -np 1/2/4, head-only vs RPC split (2026-10-03)

Issue #46 step 1. The plan is `records/plans/hub-batching-2026-10-02.md` §4
(branch `lab/hub-batching-plan`), and the desk read is
`records/evidence/2026-10-02-pooled-slots-desk-read/README.md` (branch
`lab/pooled-slots-desk-read`, draft lab PR #48). The campaign is
`tools/runs/campaigns/pooled-slots`, and every rig launch went through the door.
Every figure below is about a config tag.

## Config tags

All tags share one checkpoint, one image and one engine argv apart from the
placement:

- Checkpoint: Qwen2.5-Coder-32B-Instruct Q5_K_M (`/models/dense/…Q5_K_M.gguf`, 64 layers).
- Image: `llamacpp:b10644-L3-rpc`. It ran as image id
  `sha256:c49d9cd3e2d69c7a81305cd8ed15a7bc6cb957e90ff51413a8b864bdb5aa5841` on
  the head and on the worker, both before and after the run (`rig-before.txt`,
  `rig-after.txt`, `worker-steps.txt`, and `img=` on every CONFIG and level
  row). That is the desk read's `sha256:c49d9cd3…`, so the desk read's source
  reading of d7a207411 applies.
- Engine argv: `-ngl 99 -fa on -ctk q8_0 -ctv q8_0 -sm layer --no-warmup -lv 4`,
  plus `-np K -c K×ctx` from `@np=K` (`tools/runs/drivers/mgpu_sweep.py` `argv()`).
- Driver: 580.178.04 on both ends.

The model is not named in the plan. It is the one rpc-split used for its q5
split pair (`rpc-split/8-pair-q5-local.sh`, `9-pair-q5-rpc.sh`), and the one
today's pooled head serves (lab PR #42 `e2e/head-args-3.txt`).

| tag | placement |
|---|---|
| `q5-h` | head-only: two RTX 3060 at llama.cpp's default split |
| `q5-s` | split: the same two cards plus the worker's GTX 1660 SUPER as `RPC0` (`ggml-rpc-server -d CUDA0` on the LAN). `-dev CUDA0,CUDA1,RPC0 -ts 27,26,12`, as today's pooled head runs: RPC0 holds layers 53–63 and the output layer |
| `q5-s-out1` | split, `-dev RPC0,CUDA0,CUDA1 -ts 11,27,27`: the same per-device layer counts, with the output layer on CUDA1 (desk read cell 6) |

The arms (plan §4) are tags plus `-np`. H*K* is `q5-h` and S*K* is `q5-s`, at
`-np K` with 2048 per slot (`-c` = K × 2048). Every cell ran levels 1, 2 and 4,
with one driver invocation per cell. Rounds a, b and c each ran H1 S1 H2 S2 H4
S4, then the nulls S1N S4N H1N H4N, then desk cells 1–7, in that order. Every
arm and every null therefore has three interleaved invocations. In each
invocation the driver's warm-up request was discarded.

## Per-cell results (arms and nulls)

`agg` is the median over the three invocations, with [min–max]. `p50` is the
per-request latency (median request wall time) and `ttft_p50` the median time
to first token, both medians over the invocations. "ctx/slot" is the engine's
own `n_ctx_seq`. Source: `analysis.txt` (`instruments/analyse.py` over
`round-{a,b,c}.tsv`).

| cell | tag | -np | ctx/slot | C | agg tok/s | p50 latency s | ttft_p50 s | invocations | otok |
|---|---|---|---|---|---|---|---|---|---|
| H1 | q5-h | 1 | 2048 | 1 | 11.7 [11.7-11.7] | 8.62 | 1.36 | 3 | 101 |
| H1 | q5-h | 1 | 2048 | 2 | 13.0 [12.9-13.0] | 21.92 | 5.13 | 3 | 202,232 |
| H1 | q5-h | 1 | 2048 | 4 | 12.9 [12.9-12.9] | 44.84 | 29.69 | 3 | 206 |
| S1 | q5-s | 1 | 2048 | 1 | 9.1 [9.0-9.1] | 11.10 | 2.58 | 3 | 101 |
| S1 | q5-s | 1 | 2048 | 2 | 10.7 [10.6-10.7] | 26.69 | 6.89 | 3 | 202,232 |
| S1 | q5-s | 1 | 2048 | 4 | 10.5 [10.5-10.5] | 54.54 | 32.87 | 3 | 206,208 |
| H2 | q5-h | 2 | 2048 | 1 | 11.7 [11.6-11.7] | 8.64 | 1.38 | 3 | 101 |
| H2 | q5-h | 2 | 2048 | 2 | 16.5 [16.4-16.5] | 17.18 | 1.71 | 3 | 202 |
| H2 | q5-h | 2 | 2048 | 4 | 20.4 [19.0-21.9] | 29.33 | 9.90 | 2 (+1 with failed requests, below) | 206 |
| S2 | q5-s | 2 | 2048 | 1 | 9.1 [9.1-9.1] | 11.15 | 2.60 | 3 | 101 |
| S2 | q5-s | 2 | 2048 | 2 | 12.8 [12.7-12.8] | 22.87 | 3.71 | 3 | 202,224 |
| S2 | q5-s | 2 | 2048 | 4 | 16.0 [14.3-16.0] | 40.50 | 15.14 | 3 | 206 |
| H4 | q5-h | 4 | 2048 | 1 | 12.0 [12.0-12.0] | 8.45 | 1.18 | 3 | 101 |
| H4 | q5-h | 4 | 2048 | 2 | 16.4 [16.0-16.5] | 17.23 | 1.71 | 3 | 202,242 |
| H4 | q5-h | 4 | 2048 | 4 | 24.8 [23.5-25.8] | 27.27 | 3.69 | 3 | 206,208 |
| S4 | q5-s | 4 | 2048 | 1 | 9.4 [9.4-9.5] | 10.70 | 2.14 | 3 | 101 |
| S4 | q5-s | 4 | 2048 | 2 | 12.8 [12.8-12.8] | 22.85 | 3.72 | 3 | 202 |
| S4 | q5-s | 4 | 2048 | 4 | 17.7 [17.7-18.5] | 39.16 | 7.00 | 3 | 206,208 |
| S1N | q5-s | 1 | 2048 | 1 | 9.1 [9.0-9.1] | 11.15 | 2.60 | 3 | 101 |
| S1N | q5-s | 1 | 2048 | 2 | 10.7 [10.6-10.7] | 26.75 | 6.91 | 3 | 202,232 |
| S1N | q5-s | 1 | 2048 | 4 | 10.5 [10.5-10.6] | 54.67 | 36.75 | 3 | 206,223 |
| S4N | q5-s | 4 | 2048 | 1 | 9.4 [9.4-9.5] | 10.69 | 2.15 | 3 | 101 |
| S4N | q5-s | 4 | 2048 | 2 | 12.8 [12.7-12.8] | 22.84 | 3.71 | 3 | 202 |
| S4N | q5-s | 4 | 2048 | 4 | 18.5 [17.6-18.5] | 38.49 | 7.00 | 3 | 206 |
| H1N | q5-h | 1 | 2048 | 1 | 11.7 [11.6-11.7] | 8.64 | 1.38 | 3 | 101 |
| H1N | q5-h | 1 | 2048 | 2 | 13.0 [13.0-13.1] | 21.93 | 5.13 | 3 | 232,241 |
| H1N | q5-h | 1 | 2048 | 4 | 12.9 [12.9-12.9] | 44.84 | 29.69 | 3 | 206 |
| H4N | q5-h | 4 | 2048 | 1 | 11.9 [11.9-12.0] | 8.47 | 1.18 | 3 | 101 |
| H4N | q5-h | 4 | 2048 | 2 | 16.5 [16.4-16.5] | 17.18 | 1.73 | 3 | 202 |
| H4N | q5-h | 4 | 2048 | 4 | 23.9 [23.8-25.8] | 28.75 | 3.69 | 3 | 206 |

At C above `-np` the extra requests waited in the engine's own queue, for
example S1 at C=2 and C=4. Those rows are today's behaviour and are kept for
that. They are not a slot's throughput. `ptok` was 574 / 573 / 625 at C = 1 / 2
/ 4 on every row (the same draws). The desk cells are tabulated in
`analysis.txt`, and their readings follow below.

## Tie bar, and how it was priced

The bar is priced per rung from repeated samples of identical cells, as the
plan asks: S1 together with S1N, and S4 together with S4N, six invocations
each. The spread of a family is (max − min) / min of `agg`. The bar at a rung is
the larger of the two families' spreads. No class bar was borrowed, because
split llama.cpp over RPC is not a class in `tools/runs/derived.json`.

| C | S1+S1N agg | S4+S4N agg | bar |
|---|---|---|---|
| 1 | 9.0–9.1 (1.1%) | 9.4–9.5 (1.1%) | 1.1% |
| 2 | 10.6–10.7 (0.9%) | 12.7–12.8 (0.8%) | 0.9% |
| 4 | 10.5–10.6 (1.0%) | 17.6–18.5 (5.1%) | 5.1% |

The head-only null spreads (H1+H1N, H4+H4N) are 0.9% / 3.1% / 9.8% at
C = 1 / 2 / 4. They are used only for the round-trip reading.

## Go / no-go for step 2: **GO**

The plan's rule: on the split config, at C=2 and at C=4, `agg` of S*C* beats S1
by more than the tie bar in every invocation.

| C | round a | round b | round c | bar | worst S*C* vs best S1/S1N |
|---|---|---|---|---|---|
| 2 | S2 12.8 vs S1 10.7: +19.6% | 12.7 vs 10.6: +19.8% | 12.8 vs 10.7: +19.6% | 0.9% | 12.7 vs 10.7: +18.7% |
| 4 | S4 18.5 vs S1 10.5: +76.2% | 17.7 vs 10.5: +68.6% | 17.7 vs 10.5: +68.6% | 5.1% | 17.7 vs 10.6: +67.0% |

Every invocation beats the bar at both rungs, so the reading is GO.

**Comparability.** The lab's rule allows a ratio only between rows whose `ptok`
and `otok` match. `ptok` matches on every pair. `otok` matches at C=4 in rounds
a and b (206/206, 208/208) but not in round c (208 vs 206). At C=2 it matches in
no round: S2 had 202 / 224 / 202 against S1's 232 / 202 / 232. Temperature 0 is
not reproducible here even between identical cells: S1-a and S1N-a disagree
at C=2 in the interrupted first run of round a, and H1N-b had 241 where H1-b had
232. So the C=2 rows differ in length by up to about 30 of ~430 generated
tokens. In round b, S2 generated more tokens than S1 (224 vs 202) and was still
19.8% faster, so the C=2 gain does not depend on the length difference. The
C=4 gain is also read on matching rows (rounds a and b).

## The open prediction: does batching hide the per-token RPC round trip? **No.**

The plan's reading is the split penalty `agg(S)/agg(H)` at the same `-np` and
rung, which hides the round trip only if it narrows as `-np` grows by more than
both null spreads.

| C | -np 1 | -np 2 | -np 4 |
|---|---|---|---|
| 1 | 0.769 / 0.778 / 0.778 | 0.778 / 0.784 / 0.778 | 0.792 / 0.783 / 0.783 |
| 2 | 0.823 / 0.815 / 0.829 | 0.776 / 0.774 / 0.776 | 0.780 / 0.776 / 0.800 |
| 4 | 0.814 / 0.814 / 0.814 | 0.842 / (H2-a failed) / 0.653 | 0.787 / 0.714 / 0.686 |

The penalty does not narrow. At C=2 it widens from 0.82 (-np 1) to 0.78; at C=4
from 0.81 to 0.69–0.79. The per-request decode step shows why (`tpot.txt`,
median of (end − first token) / (gen − 1) over the REQ rows):

| busy slots | q5-h | q5-s | q5-s minus q5-h | q5-s-out1 minus q5-h |
|---|---|---|---|---|
| 1 (C=1) | 73 ms | 85–86 ms | +12 ms | +7 ms |
| 2 (H2/S2 at C=2) | 78 ms | 98 ms | +20 ms | — |
| 4 (H4/S4 at C=4) | 114 ms | 153 ms | +39 ms | +15 ms (129 ms) |

The split's extra time per step grows with the busy slots instead of being paid
once per step. Most of the growth goes when the output layer leaves the worker
(`q5-s-out1`). That fits the desk read's §Q4: the logits read back from RPC0
grow with one output per busy slot. Batching still pays on the split config
(+20% at C=2, +69–76% at C=4 over S1), but because the GPUs batch, not because
the round trip is hidden. The plan's arms start every request together, which
is the best case. Cells 4 and 5 below show how much of it real traffic keeps.

## Desk read cells (all on the split config, levels 1,2,4, three rounds)

1. **What `-c` means (D1S2, D1S4: total `-c 12288`).** The engine's own lines:
   at `-np 2`, `n_ctx_seq` = 6144; at `-np 4`, 3072; `kv_unified=false`.
   Per-device KV is CUDA0 688, CUDA1 663 and RPC0 280 MiB, identical at
   `-np 2`, `-np 4` and under `-kvu`. That is the desk read's §Q3 table
   (688.5 / 663.0 / 280.5), with the worker's share included, read off the
   engine. Per slot at -c 2048 × K the KV scales by K on every device: S4 at
   `-c 8192` is 459 / 442 / 187. So an explicit `-np` splits `-c` per slot
   (§Q1 confirmed), and the total `-c` alone sets the KV.
2. **`-kvu` (D2KVU, total 12288, `-np 4`).** `kv_unified=true`, `n_ctx_seq` =
   12288, the same KV bytes per device. `agg` at C=4 is 15.2–15.8, against
   17.8–18.9 for the split-KV D1S4 at the same total. The fill: D2FILL (pool
   3072) never filled under the workload in any round, so every request
   answered. The re-run `5-fill.sh` (pool 2048, D2FILL2048-t1..t3) failed all
   four running requests of level 4 together in 3 of 3 tries. They failed at
   one instant (each try's four `end=` within 2 ms), each with HTTP 200 and an
   in-stream error `Context size has been exceeded.` Levels 1 and 2 of the same
   cells answered. That confirms §Q1's failure mode.
3. **The held request (D3HELD: S1, `@stagger=0.5`).** It was the same in all
   three rounds (`analysis.txt` § cell 3). Requests started in arrival order
   (FIFO at C=2 and C=4), with no 5xx and every status 200. A held request
   received no byte while it waited. Its first byte came 0.19–0.27 s after the
   request ahead of it ended, and its first token 1.5–2.0 s after that. The
   silence the hub's relay and client timeouts must allow for is the whole wait
   behind the requests ahead. At C=4 the fourth request waited 65.7–65.8 s for
   its first byte and 67.6–67.7 s for its first token. One difference from
   §Q2's reading: the first byte comes **before** the first token, on every one
   of the 449 answered requests in this envelope, held or not. The lead is
   0.78–7.0 s; in D3HELD it is 1.3–2.0 s. The stream opens when the task
   starts, before its prefill, and not at its first token. A held request is
   silent only until its task starts.
4. **Gaps in slot ids (D4GAP `@id_slot=0,2,1,3` vs D4SEQ `0,1,2,3`).** The
   server took the named slots (`slots=0,2` vs `0,1`, read from its log). At
   C=2, `agg` was 11.3 with the gap against 12.8 without (−12%, all rounds).
   The per-request decode step was 130 vs 98 ms (median), so the gap made two
   ubatches per step (§Q4 item 1). At C=4 every slot is busy and the two are
   equal (18.9–19.0). Otok differs at C=2 (202 vs 206).
5. **Prefill beside decode (D5STAG, S4 with `@stagger=3`).** Against S4 (all
   requests at once), `agg` was 12.3 vs 12.8 at C=2 and 16.7–16.8 vs 17.7–18.5
   at C=4. The decode step was 106 vs 98 ms at C=2 and 166 vs 153 ms at C=4.
   `ttft_p50` fell from 7.0 to 2.3 s at C=4, because arrivals no longer queue
   on one joint prefill. The stagger also leaves slots idle at the start, so
   the `agg` gap is an upper bound on the prefill interference. The tpot gap is
   the cleaner figure.
6. **Logits read-back (D6OUT1 = `q5-s-out1` vs S4).** With the output layer on
   CUDA1 instead of RPC0, `agg` was 9.8–9.9 vs 9.4–9.5 (C=1), 14.2 vs 12.8
   (C=2) and 20.8–21.3 vs 17.7–18.5 (C=4). The decode step was 129 vs 153 ms at
   C=4. The read-back grows with busy slots (§Q4). `n_vocab` was not read from
   the GGUF, so the bytes are not stated.
7. **Prompt-cache save (D7NOCACHE: S2 with `--cache-ram 0`, read at C=4).**
   `agg` was 15.4 / 16.4 / 16.4 vs S2's 16.0 / 16.0 / 14.3. At C=4 the two-slot
   cells' `agg` moves with the order the held requests are paired in (S2 itself
   spans 14.3–16.0), so no effect is resolved at C=4. At C=1, where slot
   turnover is a single save, `ttft_p50` was 2.14 s with `--cache-ram 0`
   against 2.60 s by default (`agg` 9.5 vs 9.1). That is about 0.45 s per new
   task for the idle-slot save, which reads the slot's KV back from every
   device, RPC0 included (§Q5).

## Context ceiling per slot (q5-s), steps 4 and 6

This is a ladder on total `-c` at `-np` 1, 2 and 4, one request per load
(`ceiling.tsv`, `ceiling-retry.tsv`).

| total -c | -np 1 | -np 2 | -np 4 |
|---|---|---|---|
| 32768 | loads (32768/slot) | loads (16384) | loads (8192) |
| 40960 | loads (40960) | loads (20480) | loads (10240) |
| 45056 | loads (45056) | loads (22528) | loads (11264) |
| 49152 | refused 3/3 | refused 3/3 | refused 3/3 |

**Ceiling per slot on `q5-s`:** 45056 at `-np 1`, 22528 at `-np 2` and 11264
at `-np 4` (the last rung that loaded). The edge lies below a total of 49152 at
every `-np`. KV at a total of 45056 is CUDA0 2524, CUDA1 2431 and RPC0 1028 MiB.
CUDA0 was the fullest card at load (11787–11849 of 11909 MiB free before
load), which suggests it binds first. The refusal text only says "failed to
create context", so that is unverified. Compute buffers do not follow `-np`
monotonically. At a fixed total they are 360/296/264 MiB (32768),
400/320/280 (40960) and 260/238/300 (45056) per device for `-np` 1/2/4. At the
arms' 2048 per slot they are 240 at every `-np`. The fit has to read them per
launch rather than scale them with slots (§Q3's open item, read here).

## Deviations

- **Model.** The plan leaves the checkpoint open. Q5_K_M 32B was used: rpc-split's
  q5 split pair and today's pooled head. rpc-split's other split pair (the
  30B-A3B MoE) was not run.
- **Split placement pinned.** The split config is pinned to today's pooled head
  (`-dev CUDA0,CUDA1,RPC0 -ts 27,26,12`), where rpc-split's pair used the
  default split. Head-only uses the default split, as the pair did.
- **Round a was interrupted.** Its first door run (`2026-10-03-pooled-slots-round-a`)
  was killed after seven cells (H1-a … S1N-a). The cause was the background
  time limit of the operator's tool, not the rig. Gate 7 could not re-read the
  rig, and the run's container `…-round-a-mgpu-a` and its sidecar were left on
  srv1. Both were removed by hand, the dead claim file was deleted, and the
  partial TSV was moved aside as
  `round-a.interrupted-2026-10-03-pooled-slots-round-a.tsv` (with
  `door-round-a.interrupted.log`). Round a was re-run whole with
  `--suffix r2`. The interrupted rows are filed and not used in any reading.
- **The fill cell did not fill.** D2FILL in the rounds (`-kvu`, pool 3072) never
  exceeded its pool under the workload. A step 5 was added after round a with a
  pool of 2048, three tries. It used the same `-c` override in the extra
  (`-kvu -c 2048`, after the driver's `-c`).
- **Ceiling.** Retries and the refining rung were added as step 6, because the
  driver retries only refusals whose words are about memory, and "failed to
  create context" is not. The ladder sends one default request per load: there
  is no long `@prefill` filling a slot, as rpc-split's ctx steps had. The
  ceiling is the largest `-c` that loads and answers one request.
- **H2 at C=4 crashed once.** In H2-a (`q5-h`, `-np 2`) at level 4, all four
  connections ended at 1.92 s. The two running requests stopped after 2
  tokens; the two held requests got `RemoteDisconnected`. The container was
  removed at the end of the cell, so its log was not kept, and the cause is
  unknown. The journal on srv1 showed no Xid or OOM; `dmesg` is not readable
  there. The row is excluded from the `agg` medians and ratios, where the
  analysis drops any level with a failed request. H2-b and H2-c ran clean.
- **Draw assignment.** The driver now draws a level's prompts in index order
  before sending, so request i carries the same prompt in every cell. A level
  consumes the same draws as before.
- **Door run root.** `MCGYVR_RUN_ROOT` was set to the lab checkout. The first
  smoke attempt without it was refused at gate 5 and wrote gate 1's round into
  `product/tools/bench/rounds.json`. That change was reverted, and nothing was
  committed in `product/`.

## Not verified

- Why H2-a's server dropped every connection (no log kept).
- Which device binds the 49152 refusal (the refusal text names none).
- `n_vocab`, and so the logits bytes per slot behind cell 6.
- Whether httplib's 3600 s socket timeouts could end a held request. No wait
  here exceeded 66 s.
- The C=2 GO comparison rests on rows whose `otok` differ (see Comparability).

## Rig state

`rig-before.txt` (01:50Z) and `rig-after.txt` (07:57Z) were taken for both rigs.
Before: no running container on either rig (only the old exited ones listed
there), cards idle (srv1 2 × 11909 MiB free, srv2 5729 MiB free), no compute
apps, no lease. After: the same container list, the same free memory, no
compute apps, no lease. Started and removed during the run: the worker
`rpcw-pooled-slots` on srv2 (by hand), and the driver's
`<RUN_ID>-mgpu-a` heads on srv1 (by the driver and the door, plus the one left
by the interrupted run, removed by hand).

## Files

- `round-a.tsv`, `round-b.tsv`, `round-c.tsv`: the three rounds.
- `smoke.tsv`: step 0.
- `ceiling.tsv`, `ceiling-retry.tsv`: steps 4 and 6.
- `fill.tsv`: step 5.
- `*.run.json`: the door's run headers.
- `door-*.log`: the door's output per step.
- `scan.json`, `geometry.json`, `placement.json`: the door's data gates.
- `worker-steps.txt`: the worker's card, its argv and its image id, before and
  after each step.
- `head-args-inspected.txt`: `docker inspect` of the live head containers in
  steps 4–6. The rounds' argv is the driver's `argv()` with each label's `ctx`
  and `extra`.
- `rig-before.txt`, `rig-after.txt`: rig state before and after the run.
- `analysis.txt`, `tpot.txt`: the readings above, recomputed from the TSVs by
  `instruments/analyse.py` and `instruments/tpot.py`.
- `instruments/`: the hand-run scripts (`chain.sh` ran the steps through the
  door, plus `worker.sh`, `rigstate.sh` and `argcap.sh`).

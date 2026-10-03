# Social batching end to end, slots 4 vs 1, through the hub and the rig agent (2026-10-03)

Issue #46 step 5. The plan is `records/plans/hub-batching-2026-10-02.md` §8
(branch `lab/hub-batching-plan` @ `6dc3c300`). Step 1, the direct-to-engine
measurement, is `records/evidence/2026-10-03-pooled-slots/README.md` (branch
`lab/pooled-slots-measure` @ `cd02fc40`, draft lab PR #50). Every figure below
is said about a config tag, never about a rig.

```text
 load.py (4 users)             hub (this host, 127.0.0.1:18766)              rigs (one ssh -R each, ~67 ms RTT)
 usr1..usr4, streamed  ──►  hubtrace.py ► mcgyvr-hub serve  ──websocket──►  head agent (agenttrace.py) ─► llama-server -np N
 seed = per-request tag     queue: width = slots, turns by user                  worker agent ─► ggml-rpc-server (RPC0)
                            vps-a, vps-b: agents with no card (usr3, usr4 give to the pool; never planned on)
```

## Code under test

| what | ref |
|---|---|
| hub | AdarGit008/mcgyvr-hub `pool-head-slots` @ `76cd212` (draft #14), stacked on #8 `pool-session-width`, #5 `pool-fair-order`, #4 `pool-wait-queue`, `connect`; a detached worktree, removed after |
| rig agent | AdarGit008/mcgyvr `rig-head-slots` @ `abccb902` (draft #569), base `35d62c39`; on each rig as `~/mcgyvr-pool-tmp/product-slots` (a local clone of the rig's `product` plus a two-commit bundle), its own `.venv`; on this host from `/home/adaramir/claude/mcgyvr-product-slots` |
| agent version reported | `0.0.1.dev1308+gabccb9022` (rigs) and `0.1.1.dev875+gabccb902` (this host's clone): the same commit, `git describe` differs by clone |
| engine image (lender's setting) | `llamacpp:b10644-L3-rpc`, image id `sha256:c49d9cd3e2d6…` on head and worker in every invocation (`args/*.txt`, `rig-before.txt`) = step 1's |
| driver | 580.178.04 on both rigs |
| lab base | `mcgyvr-social` @ `cf53dc3b` (demo tooling, `tools/runs/workload.py`) |

## Config tags

One checkpoint, Qwen2.5-Coder-32B-Instruct Q5_K_M (64 layers), split by the
hub's planner over head-rig's two RTX 3060 and worker-rig's GTX 1660 SUPER as
`RPC0`. Hub settings are its defaults except the three named.

| tag | hub settings | head launched (`args/*.txt`, every invocation identical) |
|---|---|---|
| `e2e-s4` | `MCGYVR_HUB_PLANNER_TARGET_SLOTS=4`, `MCGYVR_HUB_PLANNER_DEFAULT_CTX=10240` | `-np 4 -c 40960 -fa on -ctk q8_0 -ctv q8_0 --rpc 10.211.0.2:50052 -dev RPC0,CUDA0,CUDA1 -ts 12,27,26`; engine: `n_slots = 4, n_ctx_slot = 10240, kv_unified = 'false'` |
| `e2e-s1` | `MCGYVR_HUB_PLANNER_TARGET_SLOTS=1`, the same ctx | `-np 1 -c 10240 … -dev RPC0,CUDA0,CUDA1 -ts 12,26,27`; engine: `n_slots = 1, n_ctx_slot = 10240, kv_unified = 'false'` |

The hub's `head_start` (`traces/hubtrace.jsonl`, `ev=head_start`) carried
`slots` 4 / 1, `ctx` 10240 and the devices `[rpc worker-rig 0, local head-rig 0,
local head-rig 1]` with the same tensor split. **The output layer is on a head
card in both tags**: the last `-dev` entry is `CUDA1`, a head-rig card. The
session width the hub admitted equals the slots (`q_enter.width`: 4 and 1).
`MCGYVR_HUB_CHAT_WAIT_SLOT_S` was 30 (default) in the queue cells and 900 in
the throughput cells (Deviations 4).

## Throughput: slots 4 vs 1 through the hub

Six invocations per tag (rounds a, b, c × arm and its null), interleaved
`e2e-s4, e2e-s1, e2e-s4, e2e-s1, …`; each invocation is a fresh hub and a fresh
session, a discarded warm-up (workload draw 0), then cell `c4` and cell `c8`.
`c4` sends step 1's level-4 draws (4..7), one per user, usr1..usr4; `c8` sends
draws 4..11, two per user. Requests go out 20 ms apart in that order. Every
request in every cell answered 200. Per-invocation rows: `analysis.txt`; per
request: `per-request.tsv`.

| tag | cell | agg tok/s median [min–max] | spread | p50 latency s | client TTFT p50 s | hub queue p50 s (max) | agent TTFT p50 s | ptok | otok |
|---|---|---|---|---|---|---|---|---|---|
| `e2e-s4` | c4 (C=4) | **20.12** [19.36–20.18] | 4.2% | 34.66 | 6.92 | 0.00 (0.00) | 6.08 | 625 | 208 (223 in T4-c) |
| `e2e-s1` | c4 (C=4) | **10.55** [10.52–10.67] | 1.4% | 52.18 | 31.21 | 28.71 (65.3) | 2.19 | 625 | 208 |
| `e2e-s4` | c8 (C=8) | **22.15** [22.04–22.26] | 1.0% | 53.28 | 11.57 | 9.87 (47.4) | 1.28 | 651 | 239–241 |
| `e2e-s1` | c8 (C=8) | **11.11** [11.07–11.17] | 0.9% | 83.83 | 69.31 | 66.90 (141.3) | 1.30 | 651 | 240 |

`agg` = generated tokens / (last end − first send), as step 1's driver computes
it; `ptok`/`otok` = mean prompt / generated tokens per request.

**Tie bar** (priced as step 1 did, from null replicates of one identical cell):
per cell, the larger of the two tags' spreads (max − min)/min over their six
invocations: **4.2% at c4, 1.0% at c8**. The c4 bar is set by T4-c, whose
replies averaged 223 tokens against 208 everywhere else: draw 6 ran to its cap
of 346 where every other invocation stopped it at 285 (temperature 0 is not
reproducible under batching). On otok-matched rows only, `e2e-s4` c4 spans 20.04–20.18 (0.7%).

**Verdict: `e2e-s4` beats `e2e-s1` beyond the bar in every invocation.** Worst
`e2e-s4` invocation against best `e2e-s1`: +81.4% at c4 (19.36 vs 10.67, bar
4.2%), +97.3% at c8 (22.04 vs 11.17, bar 1.0%). Paired per round: +83.5% to
+91.4% at c4, +98.1% to +100.4% at c8 (`analysis.txt` § Tie bar).

**At the default 30 s slot wait, these cells would have been refused in part.**
Of the requests above, the hub queue held longer than 30 s: 12 of 24 (`e2e-s1`
c4), 36 of 48 (`e2e-s1` c8), 0 of 24 (`e2e-s4` c4) and 16 of 48 (`e2e-s4` c8).
Those would have been 503 `pool_busy` under `chat_wait_slot_s` = 30.

### Time to first token, client side and agent side

| tag | cell | client TTFT | = hub queue | + hub→agent | + agent TTFT | + agent→hub flush | engine `prompt_ms` |
|---|---|---|---|---|---|---|---|
| `e2e-s4` | c4 | 7.06 | 0.00 | 0.035 | 6.08 | 0.78 | 5.76 |
| `e2e-s1` | c4 | 31.30 | 28.76 | 0.035 | 2.19 | 0.76 | 1.89 |
| `e2e-s4` | c8 | 11.44 | 9.81 | 0.034 | 1.25 | 0.17 | 0.83 |
| `e2e-s1` | c8 | 68.87 | 66.19 | 0.035 | 1.30 | 0.53 | 0.88 |

Medians over the request rows (s). Agent TTFT = first content bytes from the
head − the agent's receipt of `relay_request` (rig clock, `agenttrace.py`).
Flush = the hub's receipt of the first data frame − the agent putting it in its
outbox (cross-clock, srv1 offset −6.0 ms ± 33 ms, `clock.txt`). **The flush
delay is attributed to the agent's pump (`rig/agent.py:72`, `RECEIVE_SLICE_S =
1.0`; Not verified):** it is 0.04–1.26 s per request (182 relays) and inflates
the client TTFT by that much over the agent's. At c4 under `e2e-s4` the four prompts prefill together, so the agent TTFT is
~6 s against ~2 s one at a time.

### Against step 1 (direct to the engine)

`step1-reference.txt` holds step 1's n=4 rows. **Only one pair is close, and
it is not like-for-like.** Step 1's `D6OUT1` (`-np 4 -dev RPC0,CUDA0,CUDA1 -ts
11,27,27`, output on a head card) ran the same draws 4..7 at C=4: agg 20.8 /
21.3 / 21.3, ptok 625, otok 208 / 206 / 206. `e2e-s4` c4 gave 20.04–20.18 on
rows with ptok 625 and otok 208, which match `D6OUT1-a` (20.8): about 3–4%
lower through the hub. The two differ in more than the path: `-ts 12,27,26`
against `11,27,27`, 10240 against 2048 tokens of context per slot, and a hub
and agent relay (with its flush) in between. So the gap is not a measurement
of the hub's cost. `e2e-s1` has no step 1 counterpart: step 1's `-np 1` cells
(S1, S1N: 10.5–10.6 at C=4) put the output layer on the worker. Step 1 ran no
C=8, so `c8` is not comparable to anything there.

## The wait queue (`chat_wait_slot_s` = 30)

All in `rows/q*.jsonl`, joined to the hub trace in `analysis.txt` § Queue.

- **Extras wait; no 503 inside the bound.** At `e2e-s1`, six requests at once
  (burst-q1-a): one served, five queued, waits 3.2–16.1 s, all 200. At
  `e2e-s4`, eight at once (burst-q4-a): four served at once, four queued
  ~6.0 s, all 200. In the throughput cells (bound 900 s) no request was
  refused at any wait up to 141 s.
- **Past the bound: 503 `pool_busy`, `Retry-After: 1`.** At `e2e-s1`, a
  600-token holder (usr1) and then a waiter (usr2): the waiter got `503`,
  code `pool_busy`, "the session is serving as many requests as it may",
  `Retry-After: 1`, after 30.02 s (`rows/q1-busy2-*.jsonl`; trace `q_exit
  outcome=busy waited=30.000`). A first try with a shorter holder, which
  stopped at 347 tokens, let the waiter in at 29.17 s, inside the bound. That
  row is kept (`rows/q1-busy-*.jsonl`).
- **Client disconnect while queued: 499.** At `e2e-s4`, four holders, then
  usr1's fifth request, whose client closed its socket after 5 s: the hub
  cancelled the wait (`q_exit outcome=CancelledError waited=4.993`) and built
  `499 client_closed_request` (`http_error status=499`). The next waiter was
  queued with `queued=0` and admitted the moment the first holder freed a
  relay (13.6 s, `rows/q4-hangup*.jsonl`). uvicorn wrote no access line for
  the 499, because its client was gone. The same test at `e2e-s1`
  (`rows/q1-hangup*.jsonl`) ran before the `http_error` trace existed: it
  shows the cancel and the clean hand-off (next admitted at 16.06 s, as the
  holder ended), but not the 499 itself.

## Order of service (equal weights, the 1.0 placeholder)

| cell | arrival at the hub | served (the hub's admissions) |
|---|---|---|
| burst-q1-a, `e2e-s1` | usr1 usr1 usr2 usr2 usr3 usr3 | **usr1 usr2 usr3 usr1 usr2 usr3** |
| burst-q4-a, `e2e-s4` | usr1 usr1 usr2 usr2 usr3 usr3 usr4 usr4 | usr1 usr1 usr2 usr2 (at once, seats free), then **usr3 usr4 usr3 usr4** |

Users took alternating turns, not arrival order. In burst-q4-a the four
waiters were handed out within 0.8 ms when four relays freed together. The
order is the queue's, read from `q_exit` in time order. In the throughput
cells each user had the same number of requests (one in c4, two in c8), so
per-user shares are equal by construction. Their waits differ by arrival
position (`analysis.txt`).

**Weighted turns were not exercised.** In this stack every weight is the
placeholder 1.0 (`contribution_weight`, hub#5). The real weight comes from the
credits ledger, which lives on another session's branches. Weighted behaviour
rests on hub#5's unit tests (`tests/test_pool_queue.py` @ `dc9d626`):
`test_twice_the_weight_gets_about_twice_the_turns`,
`test_a_small_weight_still_gets_its_turns`,
`test_a_user_who_comes_back_has_not_banked_turns`,
`test_users_with_equal_weights_take_turns`,
`test_the_default_weight_seam_weighs_everyone_the_same`.

## Rig cap: no `busy` from the head

Over all 182 relays the head agent took (queue and throughput cells), the
agent refused none (`a_request taken=false`: 0). The hub received no
`relay_end` with code `busy`, and no client saw a 502. The most relays active
at once on the head rig was 4 under `e2e-s4` and 1 under `e2e-s1`. Right
after each admission the hub held at most `width` relays (`analysis.txt`
§ Rig cap). The hub admits only `width` = slots, and the agent's per-head cap
(the same slots) was never hit.

## Rig state

`rig-before.txt` / `rig-before-extra.txt` (09:11Z) and `rig-after.txt` /
`rig-after-extra.txt` (10:41Z), by `instruments/rigstate.sh` (from
`lab/pooled-slots-measure`) and `instruments/rigextra.sh`.

- **Before:** no running container on either rig (only the old exited ones),
  no compute apps, cards idle (srv1 2 × 11909 MiB free, srv2 5729 MiB free),
  no lease, no agent or engine process, nothing on 18765/18766. The product
  checkout was `ladder-relief-rungs` @ `12fa907c1`. Nothing GPU-using was
  running, so the run went ahead.
- **After:** the same `docker ps -a`, the same card and compute-app readings,
  no lease, and the image list identical to the baseline on both rigs (ids and
  tags). `~/mcgyvr-pool-tmp` lists the same entries, and `product` is still
  `ladder-relief-rungs` @ `12fa907c1`.
- **Started and removed by this run:** `product-slots`, `e2e-slots` (agent
  log, credentials for this run's hub, srv2's 4.0 GB tensor cache) and
  `product-slots.bundle` under `~/mcgyvr-pool-tmp` on each rig
  (`instruments/rigclean.sh`); the pooled containers (removed by the agents,
  none left, `teardown.txt`); the tunnel image `mcgyvr-tunnel:e072940be18f`,
  which the agents built on each rig (`docker rmi`, no container used it).
  On this host: the hub worktree `/home/adaramir/claude/mcgyvr-hub-e2e`, the
  two no-card agents, the tunnels and the state directory
  `~/.local/state/mcgyvr-demo-slots-e2e` (database, `secrets.json`), all
  removed. live-b's hub (pid 1977235, port 18765,
  `~/.local/state/mcgyvr-demo`) was not touched.
- **Left behind:** `uv sync` wrote entries into the rigs' shared
  `~/mcgyvr-pool-tmp/uv-cache` (the editable build and interpreter info).
  They are cache entries, left in place.

## Deviations

1. **Context per slot 10240, not step 1's 2048.** At 2048 the planner placed
   the model on head-rig alone at both targets (`plan-preview/`: "Rigs 1",
   33 + 31 layers), which is not the split this step asks for. The split
   holds at both targets only between 9,030 (the most head-rig alone holds at
   one slot) and 10,963 (the most four slots hold split), so 10240 was used.
   Step 1's comparison is affected (above).
2. **Evidence directory** is `…-pooled-slots-e2e` as this task named it. Plan
   §8 says `…-pooled-social-e2e`.
3. **Four users, two of them giving a rig with no card.** The hub refuses
   other people's rigs to a user who lends none (`not_giving_pool`), so
   tools/demo's `requester` cannot use the pool. usr3 and usr4 each own an
   agent on the hub's host that lends the worker role and has no card. The
   planner never placed a layer on them: every `head_start` lists only
   head-rig and worker-rig. Handles are `usr1..usr4`: the first bootstrap, with
   two-letter handles, was refused 422 and created nothing.
4. **`chat_wait_slot_s` = 900 in the throughput cells,** so every request was
   served and `agg` is over whole cells. The 30 s default is exercised in the
   queue cells; how much of each throughput cell it would have refused is
   counted above.
5. **Not `tools/demo/demo-up` as is.** It hard-codes `~/mcgyvr-pool-tmp/e2e`,
   `../product` and port 18765, all live-b's. `instruments/hub.sh` and
   `instruments/agents.sh` follow its method (hub on loopback, one `ssh -R`
   per rig, `rig join` with the token over stdin into a 0600 file, then
   `rig run`) with the run's own folders, port 18766 and state directory.
   Switching tags restarts the hub after stopping its session through the
   API, waiting until no pooled container is left, so no hub-restart orphan
   arises.
6. **Instrumented processes.** This hub logs nothing per request, so it ran
   under `instruments/hubtrace.py` and the head agent under
   `instruments/agenttrace.py`: observational wrappers that time the request
   path and log no content. The worker agent and the no-card agents ran plain.
   The `http_error` wrapper was added after the q1 cells (Deviations 7).
7. **The 499 at `e2e-s1` is shown by its cancel, not by the 499 line,** which
   uvicorn does not log. It was re-run at `e2e-s4` with the trace that records
   it.
8. **The hub ran on this host, not the rigs' LAN.** Each rig reached it through
   an `ssh -R` tunnel at ~67 ms RTT (hub→agent median 35 ms). Every relayed
   frame pays that, which a LAN hub would not.
9. **The workload is step 1's** (`tools/runs/workload.py`, drawn in UID order,
   system prompt split off, temperature 0, `max_tokens` = the draw's cap),
   sent through the hub's OpenAI endpoint with `stream_options.include_usage`.
   The queue cells use a short counting prompt with a small cap instead.
10. **No lab code outside `records/`.** Everything added is an instrument of
   this record, and `records/` is outside the lab gate (`Makefile`). So no
   RED/GREEN cycle applied. The gate was still run (PR).

## Not verified

- That the flush figure is the pump's `RECEIVE_SLICE_S`: it is consistent with
  it (0.04–1.26 s), but the pump itself was not traced, and the excess above
  1 s plus the ~33 ms one-way trip (up to ~0.2 s) is not accounted for.
- Per-device KV and compute buffers. The head runs at default verbosity, so
  only `n_slots`, `n_ctx_slot` and `kv_unified` were read from its log.
- The fit margins at ctx 10240: whether `e2e-s4` loads at other contexts was
  not tried beyond the planner's preview.
- Weighted turns with real weights (above).
- Reply content: token counts were compared, the text was not.
- NAT traversal and the relay: both rigs share a LAN, and every session took
  the direct path.
- How many of a cell's requests the hub would have refused at the 30 s
  default if they had been sent with it: the counts above are queue waits
  measured at 900 s. A refusal frees a seat earlier and changes the waits after
  it.

## Files

- `rows/*.jsonl`: one line per request from `load.py` (client times, status,
  code, Retry-After, usage, engine timings). `q1-*`/`q4-*` are the queue cells,
  `T{4,1}{,N}-{a,b,c}-{warm,c4,c8}` the throughput cells.
- `traces/hubtrace.jsonl`, `traces/agenttrace-srv1.jsonl`: the request-path
  timestamps (no content).
- `per-request.tsv`, `analysis.txt`: everything above, recomputed by
  `instruments/analyse.py` from the files here.
- `args/*.txt`: the containers as launched, and the head's own slot lines, per
  invocation.
- `plan-preview/`: the hub's plan preview per context at targets 4 and 1.
- `step1-reference.txt`: step 1's n=4 rows used for the comparison.
- `logs/`: the hub's access log with start/stop markers, and the four agents'
  logs (token prefixes redacted as `mhr_<redacted>_`).
- `campaign.log`, `teardown.txt`, `clock.txt`, `rigprep-srv{1,2}.txt`,
  `rig-{before,after}{,-extra}.txt`.
- `instruments/`: `hub.sh`, `agents.sh`, `ctl.py`, `load.py`, `campaign.sh`,
  `hubtrace.py`, `agenttrace.py`, `argcap.sh`, `clock.sh`, `rigprep.sh`,
  `rigclean.sh`, `rigstate.sh` (from `lab/pooled-slots-measure`),
  `rigextra.sh`, `analyse.py`.
- No token, key, cookie or database is included. The session tunnels'
  WireGuard keys appear in no file here.

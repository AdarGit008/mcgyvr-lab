# Social batching on the hub — planned 2026-10-02

**Issue #46. PLAN-ONLY. Nothing has been launched or merged, and nothing here
authorises a launch.** Step 3 is built as a draft PR. §2 gives each step's
state. The owner approved this work plan on 2026-10-02. It
covers many users' requests on one pooled session, sent through the hub. Solo
batching (one user's own rigs, `n=`, the local-exhaustion line) is #32. Its plan
is `records/plans/request-batching-2026-10-01.md`, and nothing in it is restated
here.

**Open prediction, not fact:** serving several requests at once on a pooled head
hides the per-token RPC round trip across rigs. Each decode step would then pay
the round trip once for every slot, not once per request. Step 0 read the
mechanism in source (§3). Only the wall-clock answer is left, and Step 1
settles that. Step 3 (the wait queue) goes ahead of the measurement, by owner
approval. It removes the instant refusal even at one slot, so it does not
depend on the answer.

**Citations.** Each one names its repository and commit:

| prefix | repository | ref |
|---|---|---|
| `hub:` | AdarGit008/mcgyvr-hub, branch `connect` (draft mcgyvr-hub#1) | `1d59722` (`main` is `5a85d0c`) |
| `rig:` | AdarGit008/mcgyvr, branch `mcgyvr-connect` (draft mcgyvr#564, stacked on #562) | `11415cc6` |
| `hub#4:` | AdarGit008/mcgyvr-hub, branch `pool-wait-queue` (draft mcgyvr-hub#4, base `connect`) | `57de2ffe` |
| `lab#42:` | this repository, branch `mcgyvr-social` (draft lab PR #42, unmerged) | `cf53dc3b` |
| `lab#48:` | this repository, branch `lab/pooled-slots-desk-read` (draft lab PR #48, unmerged) | `5c1ef3bd` |
| no prefix | this repository, `main` | `b242f46a` |

**"The desk read"** below means Step 0's record,
`lab#48:records/evidence/2026-10-02-pooled-slots-desk-read/README.md`. It is
cited by its sections, §Q1 to §Q4.

---

## 1. What exists

This is `connect` as cited. A row that hub#4 (Step 3) changes says so.

```text
client ─ POST /v1/chat/completions ─► HUB (one process, state in memory)
  rate: 60 req / 60 s per user ............................ else 429
  in flight: 2 per user, held for the whole request ........ else 429
  _decide: join a running session of the model, fewest relays first
  lease: relays < session_max_relays (4) ................... else 503 pool_busy, Retry-After 1
      │  one websocket per rig; requests multiplexed by request_id, never merged
      ▼
RIG AGENT: active relays < MAX_ACTIVE (4) .................. else relay_end busy → 502
      ▼
llama-server -np 1 -c <ctx>  (+ --rpc to workers on other users' cards)
  → one slot; whichever user sent the request
```

| fact | where |
|---|---|
| The hub is one process, and its live state is in memory | `hub:README.md:47-49`, `hub:src/mcgyvr_hub/pool_sessions.py:23-24` |
| Per-user rate is 60 per 60 s, in fixed windows. Every attempt counts, a refused one included | `hub:src/mcgyvr_hub/config.py:35`, `hub:src/mcgyvr_hub/ratelimit.py:45-59`, `hub:src/mcgyvr_hub/completions.py:217-225` |
| At most 2 in flight per user. The slot is taken **before** the lease and released when the completion closes, so a request that waits keeps holding it | `hub:src/mcgyvr_hub/config.py:120`, `hub:src/mcgyvr_hub/ratelimit.py:75-96`, `hub:src/mcgyvr_hub/completions.py:226-235` |
| Join, don't plan: a joinable session is returned whether or not it is full, the ready ones with the fewest relays first | `hub:src/mcgyvr_hub/pool_sessions.py:463-479` |
| A rig is in at most one active session | `hub:src/mcgyvr_hub/models.py:371-383`, `hub:src/mcgyvr_hub/protocol.py:18` |
| `session_max_relays = 4`, a constant for every session | `hub:src/mcgyvr_hub/config.py:74` |
| The full-session refusal: `SessionError(BUSY, retry_after_s=1)`, counted and released around the yield. hub#4 makes it a bounded wait first (§6) | `hub:src/mcgyvr_hub/pool_sessions.py:690-703`; `hub#4:src/mcgyvr_hub/pool_sessions.py:789-822` |
| `BUSY` maps to 503 `pool_busy`, and `retry_after_s` becomes the `Retry-After` header | `hub:src/mcgyvr_hub/completions.py:127-134`, `hub:src/mcgyvr_hub/api/openai.py:49-53` |
| Other `BUSY` refusals, which are not the full-session case: a rig is reconnecting, or the model's rigs are in another session (`_RETRY_AFTER_S = 5`) | `hub:src/mcgyvr_hub/pool_sessions.py:70`, `:678-684`, `:719-724` |
| The ready-wait is separate: up to `chat_wait_ready_s` (20 s) for a loading session, then 503 `model_loading` | `hub:src/mcgyvr_hub/completions.py:237-241`, `hub:src/mcgyvr_hub/config.py:117`, `hub:src/mcgyvr_hub/pool_sessions.py:729-757` |
| The idle sweep stops a ready session only when it has `relays == 0`. hub#4 also spares a session that has waiters | `hub:src/mcgyvr_hub/pool_sessions.py:299-310`; `hub#4:src/mcgyvr_hub/pool_sessions.py:358-371` |
| `PoolSessions.drain` waits for the hub's own background tasks. It is **not** a fleet drain, and no fleet drain exists. hub#4 adds the hold that a drain would use, `hold()` / `resume()`, and nothing calls it yet | `hub:src/mcgyvr_hub/pool_sessions.py:276-282`; `hub#4:src/mcgyvr_hub/pool_sessions.py:725-739` |
| Nothing watches the client's HTTP connection while `start` waits. hub#4 adds `while_connected`, which cancels the start on `http.disconnect` | `hub:src/mcgyvr_hub/api/openai.py:134-137`; no hit for `is_disconnected` or `http.disconnect` in `hub:src/`. `hub#4:src/mcgyvr_hub/completions.py:275-291`, `hub#4:src/mcgyvr_hub/api/openai.py:134-141` |
| `n` must be 1 | `hub:src/mcgyvr_hub/completions.py:75` |
| `HeadStartBody`: `session_id`, `model`, `ctx`, `devices`, `tensor_split`, `n_gpu_layers`, `split_mode`. No slot field. The hub fills it at `_head_start` | `hub:src/mcgyvr_hub/protocol.py:664-674`, `hub:src/mcgyvr_hub/pool_sessions.py:1193-1223` |
| Wire compatibility: a new optional field keeps `v = 1`, and receivers ignore unknown fields. An optional behaviour is used only with an agent that lists it in `capabilities.features` | `hub:src/mcgyvr_hub/protocol.py:148-149`, `:55-57` |
| The planner's memory model charges one `ctx` of KV per block on each device: `k * (block_bytes + ctx * kv_layer_bytes)`, plus a compute buffer that grows with `ctx` | `hub:src/mcgyvr_hub/planner.py:6-10`, `:279-283` |
| In the planner, `_slots` already means card placements for layers, not request slots | `hub:src/mcgyvr_hub/planner.py:355` |
| Hitchhike: a rig runs its owner's model, and others' requests "may ride in spare slots". No rider cap exists in `hub:src/` | `hub:src/mcgyvr_hub/access.py:7-8`, `hub:src/mcgyvr_hub/models.py:41` |
| Rig: `MAX_ACTIVE = 4` ("the head serves one at a time"), one `Relays` per agent built with the default, and `relay_end` `busy` past it | `rig:src/mcgyvr/rig/relay.py:43-44`, `:126-129`; `rig:src/mcgyvr/rig/verbs.py:213` |
| The rig's `busy` reaches the client as 502 `upstream_error` "(busy)" | `hub:src/mcgyvr_hub/agents.py:339-345`, `hub:src/mcgyvr_hub/completions.py:147-152` |
| Rig: `head_argv` passes `-np 1` and `-c <ctx>`, with `--rpc` when there are workers. `HeadSpec` has no slot field | `rig:src/mcgyvr/sandbox/pooled.py:656-659`, `:671-672`, `:454-470` |
| Rig: `head_start` is read field by field. An unknown field is dropped, and `ctx` goes straight to `-c` | `rig:src/mcgyvr/rig/sessionwire.py:496-550`, `rig:src/mcgyvr/rig/session.py:861-875` |
| Rig: the head's image is the rig owner's lend setting, not a product pin | `rig:src/mcgyvr/rig/session.py:863`, `rig:src/mcgyvr/rig/sharing.py:82` |
| Evidence: a pooled head launched with `-np 1 -c 12288 ... --rpc` | `lab#42:records/evidence/2026-10-02-pooled-e2e/e2e/head-args-3.txt:13` |
| Evidence: that run's head lent on `llamacpp:b10644-L3-rpc` | `lab#42:records/evidence/2026-10-02-pooled-e2e/live/run2.agent-srv1.out:3` |

So on `connect` the hub admits up to four relays into a one-slot head and
refuses the fifth at once. The head holds relays two to four in its own queue
(the desk read §Q2). With hub#4 the fifth waits in the hub's queue instead.
Nothing yet weighs what a user lends.

## 2. The plan

```text
 Step 0  desk read (llama.cpp source) ───────┐
                                             ├──► Step 1  measure ──GO──► Step 2  multi-slot head
 lab PR #42 rpc-split tooling ───────────────┘         (needs product #562 → #564, hub `connect`)

 Step 3  wait queue (hub `pool-wait-queue`, off `connect`) ──► Step 4  order of service
                                                                  (weight seam; ledger later)

 Steps 2 + 4 ──► Step 5  e2e evidence through the real hub and rig agent
```

**Order.** Steps 0 and 3 ran first, in parallel. Step 4 follows Step 3. Step 1
needs lab PR #42's tooling. Step 2 needs Step 1's GO and the product branches
#562 → #564. Step 5 reads whatever has landed by then. #32 stays separate.

**State, 2026-10-02:**

| step | state |
|---|---|
| 0 | done: the desk read, draft lab PR #48 (§3) |
| 1, 2, 5 | not started |
| 3 | built: draft mcgyvr-hub#4 (§6) |
| 4 | in progress on hub branch `pool-fair-order`, base `pool-wait-queue` |

**Build steps follow the test-first loop by hand** while `wf` is paused: a
failing test, shown failing, then the change, shown passing, then the repo's own
gate, with its real output in the PR.

## 3. Step 0 — desk read, no rig

**Rules it obeys:** `okf/must-read/touching-engine.md`. Its floors are the pinned
engine's, so they are re-read from source.

Read the llama.cpp build the pooled head runs. The product does not pin it,
because the image is the lender's setting (§1). The build is the one the pooled
evidence ran, `llamacpp:b10644-L3-rpc` (§1), which is also the rpc-split image
(`lab#42:tools/runs/campaigns/rpc-split/_rpc.sh:24`). Record its digest.

1. **`-np N` and `-c`.** Is `-c` split into `c/N` per slot, or is the KV unified
   and shared across slots? Is that a default that a flag (or the build) changes?
   The lab's own driver already says "llama.cpp divides -c across slots"
   (`tools/runs/drivers/mgpu_sweep.py:25-26`). That is the driver's prose, not
   evidence, so it is checked here.
2. **`-np 1` and excess requests.** Does the server queue a request that finds
   every slot busy, or refuse it? If it queues, where, and how deep?
3. **Per-slot KV across `--rpc` devices.** Does each layer's KV, for every slot,
   sit on the device that holds that layer, an RPC worker's card included? Or
   does any of it stay on the head?

**Done: the evidence is the desk read**, in
`records/evidence/2026-10-02-pooled-slots-desk-read/` (draft lab PR #48). It
pins the build by commit and image id, and leaves open whether the tag was
rebuilt since (its "Engine version" section). Step 1's `img=` stamp is the
run's own record of the image. As in #32's Gate 0, a read is conclusive only
when it quotes file:line ranges inside that build and states the conclusion
each one supports.

**What each answer moves**, with the answer that held:

| read | held? | moves |
|---|---|---|
| (1) split per slot | **yes**, for an explicit `-np` (§Q1) | `HeadStartBody.ctx` becomes the per-slot window, and the rig passes `-c = slots × ctx` (the driver's rule, `mgpu_sweep.py:600`) |
| (1) unified | only with `-kvu`, or `-np` left on auto (§Q1) | not Step 2's launch (§5). Step 1 reads `-kvu` as an arm of its own (§4) |
| (2) queues | **yes**: FIFO, no bound, no engine timeout (§Q2) | today the head queues relays two to four. The hub's queue (Step 3) becomes the only *ordered* queue, and relays above the slot count are not sent |
| (2) refuses | no | — |
| (3) KV on the layer's device | **yes**, the RPC worker included (§Q3) | the planner charges `slots ×` KV on every device, workers included (`planner.py:6-10` already charges KV per device) |
| (4) one batched decode over RPC | a reading, not a measurement (§Q4) | Step 1 prices what splits the batch and what grows with it (§4) |

## 4. Step 1 — measure

**Rules it obeys:** `okf/must-read/reading-results.md`,
`okf/must-read/touching-engine.md`, `okf/must-read/touching-rigs.md`. Every
figure is said about a config tag, never about a rig (`okf/must-read/always.md`).

### Instrument: rpc-split's `rpc_serve` over `tools/runs/drivers/mgpu_sweep.py lcp`

Reuse lab PR #42's rpc-split campaign as it stands. `rpc_serve`
(`lab#42:tools/runs/campaigns/rpc-split/_rpc.sh:30-46`) runs `mgpu_sweep.py lcp`
on the rpc-split image, with the worker given as `--rpc` in the cell's extra.
The pair steps already compare head-only against head plus worker, at one window
and one draw (`lab#42:tools/runs/campaigns/rpc-split/9-pair-q5-rpc.sh:2-5`,
`:24`). The driver already emits what this step reads:

- per level: `agg` (aggregate tok/s), `p50` (per-request latency), `ttft_p50`,
  `dec`, `ptok`, `otok`, `early_stop`, `failed` (`mgpu_sweep.py:821-834`);
- per cell: `CONFIG` with `img=` and llama.cpp's per-device KV and compute
  buffers (`mgpu_sweep.py:53-57`, `:759`).

**One addition, a cell directive `@np=K`.** Today `-np` is the widest level
(`mgpu_sweep.py:714`), so a `-np 1` head cannot be offered two or four
concurrent requests. `@np=K` pins `-np K` (and `-c = K × ctx`, because an
explicit `-np` splits `-c` per slot, the desk read §Q1), independent of the
levels. It is parsed with the other `@` directives (`mgpu_sweep.py:28-41`,
`parse_extra` at `:185`). It lands with a lab test under `make check`.

**Three more, for the desk read's cells below**, each with its own lab test:
per-request send and first-byte times (the driver prints only per-level
summaries, `mgpu_sweep.py:821-834`); a slot id per request (`id_slot`, which
the driver does not send); and a staggered start (a level's requests start
together, `mgpu_sweep.py:443-458`).

**A constraint carried over:** the driver refuses a head that does not show two
cards (`mgpu_sweep.py:702-703`). The head-only config is therefore the head's
two cards, and the split config is those two cards plus the worker over `--rpc`.

### Arms: one checkpoint, one image, the same prompt mix

Use one checkpoint that both configs can hold, as the pair steps do. Every cell
runs the **same level list, `1,2,4`**, so that prompt draws line up across arms
(`reading-results.md`: the draw desyncs when the level list changes). Slots are
pinned with `@np`.

| arm | config | `-np` | what it stands for |
|---|---|---|---|
| **H1** | head-only | 1 | a one-slot head, no RPC |
| **H2**, **H4** | head-only | 2, 4 | slots without RPC |
| **S1** | split | 1 | today's pooled head (§1) |
| **S2**, **S4** | split | 2, 4 | Step 2's head |
| **S1-Null**, **S4-Null** | split | 1, 4 | S1 and S4 again, to price the tie bar |
| **H1-Null**, **H4-Null** | head-only | 1, 4 | H1 and H4 again, for the round-trip reading only |

- **Matched concurrency.** At each rung C (1, 2, 4), every arm got the same C
  concurrent requests. A rung above an arm's `-np` is held in the server's own
  queue (the desk read §Q2). That is today's behaviour in S1 at C = 2 and 4, so
  those rows are kept, stamped with their `-np`, and read as such. They are not
  read as a slot's throughput.
- **One cell per driver invocation, arms interleaved** (H1, S1, H2, S2, H4, S4,
  the Nulls, the desk read's cells, then again), never in blocks
  (`touching-engine.md`).
- **Per-slot KV is multiplied on every device.** At a fixed per-slot ctx,
  `-c = K × ctx` multiplies the KV by K on every device, the RPC worker
  included (the desk read §Q3). The window is one at which S4's `4 × ctx` fits
  on every device of the split config, the worker included.
- **Comparable rows only:** a ratio is quoted only between rows whose `ptok` and
  `otok` match.
- **Warm-up discarded, and several invocations per arm.** No single first-request
  number is read.
- **Context ceiling, a cell family of its own:** for each `-np` on the split
  config, a per-slot ctx ladder up to the first refusal. The refusal is the
  measurement, and a refusal is retried three times before it is believed
  (`touching-rigs.md`, as in rpc-split's `2-ctx`/`5-ctx-fine` steps). Read the
  engine's own KV buffer line in `CONFIG` against `slots × ctx`. That line is the
  readback for Step 0 (1) and (3). Read the compute buffers against `-np` too:
  whether they grow with it is open in the desk read (§Q3).
- **The rig after:** kill what was started. The worker is removed by hand
  (`_rpc.sh:5-16`).

### Cells the desk read adds

Each is one variable against its own control, on the split config, with the
same level list and draws as the arms:

1. **What `-c` means.** S2 and S4 at a fixed total `-c` of 12288 (a cell ctx of
   12288 / K), beside the per-slot arms. The engine's `n_ctx_seq` and
   per-device KV lines, the worker's included, are read against §Q1 and §Q3.
   Step 2's choice of what `HeadStartBody.ctx` means reads this.
2. **`-kvu`, an arm of its own.** S4 with `-kvu` at the same total `-c`, never
   mixed into the split-KV numbers. One cell fills the shared pool on purpose,
   to confirm the failure mode in §Q1: every running request fails together.
   Like any refusal, it is retried three times before it is believed.
3. **The held request.** S1 at C = 2 with per-request times: no 5xx, starts in
   arrival order, and no byte before the first token (§Q2). The held request's
   time to first byte is the silence the hub's relay and client timeouts must
   allow for (§5).
4. **Gaps in slot ids.** S4 with its busy slots on non-consecutive ids, against
   the same load on consecutive ids (§Q4, first of its three items).
5. **Prefill beside decode.** One slot prefills while the others decode,
   against decode only (§Q4, second item). This is also the realistic load.
6. **Logits read-back.** The logits read back each step grow with the busy
   slots, and cross RPC when the worker holds the output layer, as it does in
   today's pooled launch (§Q3, §Q4). A pair of S4 cells differs only in which
   device holds the output layer.

### Go / no-go

Read at each rung every arm ran, never as one number:

1. **GO on Step 2** only if, on the **split** config, at C = 2 and C = 4,
   `agg` of S*C* beats S1 by more than the tie bar in every invocation. The bar
   is priced from the S1-Null and S4-Null replicates for `agg` at that rung.
   Split llama.cpp over RPC is none of the classes in `reading-results.md`, so
   no class bar is borrowed. `warm_decode_class_pct` and `prefill_class_pct` in
   `tools/runs/derived.json` judge other fields. `p50` and `ttft_p50` go beside
   the decision in the per-rung table.
2. **The open prediction.** At each C, take the split penalty `agg(S)/agg(H)` at
   the same `-np`. If the penalty narrows as `-np` grows, by more than both
   configs' own null spreads, then batching hides the round trip. If not, it does
   not. Either is a recorded result. The arms start every request together,
   which is the best case for §Q4. Cells 4 to 6 say how much of it real
   traffic keeps.
3. **Otherwise NO-GO:** Step 2 is not built, and the queue (Steps 3 and 4) runs
   on a one-slot head.

The run record goes in `records/evidence/<run date>-pooled-slots/`, shaped like
rpc-split's.

## 5. Step 2 — multi-slot head (after GO)

Product branch `mcgyvr-connect` (mcgyvr#564, stacked on #562) and hub branch
`connect` (draft mcgyvr-hub#1). It travels as `okf/must-read/the-split.md` says:
a product PR from `product/`, then `make product-check` and `make guard`.

```text
hub planner ── slots × ctx-per-slot KV fit ──► Plan.slots
     │
     ▼
HeadStartBody.slots (optional, default 1) ──► rig HeadSpec.slots ──► head_argv: -np slots, -c slots × ctx, no -kvu
     │
     ├─► hub lease: relays < plan.slots           (was session_max_relays = 4)
     └─► rig Relays: active < the session's slots (was MAX_ACTIVE = 4)
```

- **Wire.** `HeadStartBody.slots` is an optional field with default 1, which is
  additive under `v = 1` (`protocol.py:148-149`). An older agent drops it
  silently and launches `-np 1` (`sessionwire.py:496-550`, `pooled.py:656-657`).
  So the hub sends `slots > 1` only to an agent that lists a slots feature in
  `capabilities.features` (`protocol.py:55-57`). Otherwise the hub would admit N
  relays into one slot.
- **Split KV, not `-kvu`.** An explicit `-np` gives each slot its own window
  of `-c / slots` (the desk read §Q1), so `-c` is `slots × ctx` for the same
  context per user. `-kvu` would keep the total at `ctx` but share it, and a
  full shared pool fails every running request together (§Q1). Step 1's `-kvu`
  arm is read on its own and does not change this launch by itself.
- **Planner.** It charges `slots × ctx-per-slot` of KV per block on every device
  the layer sits on, the RPC worker included (the desk read §Q3). So a worker
  that fits one slot's KV may not fit four. It recalibrates the compute-buffer
  term against Step 1's `CONFIG` buffer readings, as the existing calibration
  cases do (`planner.py:84-90`). Whether that term grows with slots is open
  (§Q3). The new count gets a name other than `_slots` (`planner.py:355`).
- **Caps follow slots.** The hub's lease cap becomes the session's slot count,
  not `session_max_relays` (`config.py:74`). The rig's cap becomes the head
  session's slot count, not the per-agent `MAX_ACTIVE` (`relay.py:43-44`,
  `verbs.py:213`). The rig's refusal stays as the backstop. The cap must
  equal the slot count exactly. The engine holds any request past its slots in
  its own FIFO, with no bound and no timeout (the desk read §Q2), and the hub's
  order of service (Step 4) cannot reach it there. Until this lands, hub#4's
  cap is still 4 over a one-slot head, so the hub orders only the requests past
  the fourth relay.
- **Silence while held.** A request the engine holds sends no byte until its
  first token (§Q2). The relay's and client's idle timeouts must allow for that
  silence. With caps equal to slots, the wait moves to the hub, where
  `chat_wait_slot_s` bounds it (§6).
- **Left to Step 1's cells** (§4): whether the hub should name slot ids to keep
  busy slots consecutive (cell 4), and which device should hold the output
  layer (cell 6). Today the engine picks the slot (§Q4).
- **How many slots a plan asks for** is decided in that PR, as a hub setting with
  the planner's fit as its ceiling. It is not decided here.

## 6. Step 3 — wait queue (owner-approved ahead of the measurement)

Hub branch `pool-wait-queue` off `connect`, as a draft PR with base `connect`.

**Built:** draft mcgyvr-hub#4. Its new setting, `chat_wait_slot_s`, defaults to
30 s (`hub#4:src/mcgyvr_hub/config.py:118`). The ordering seam is
`_Queue._next()` (`hub#4:src/mcgyvr_hub/pool_sessions.py:190-193`).

```text
lease(user, model)
  └─ _find_or_start → live session
       relays < cap ?  ── yes ─► relay
            │ no
            ▼
       enqueue (user, arrival) ── slot freed (lease exit) ──► dequeue next ─► relay
            │
            ├─ waited chat_wait_slot_s ──► 503 pool_busy, Retry-After
            └─ client gone / task cancelled ──► removed, no slot taken
```

- **Where:** the full-session refusal in `PoolSessions.lease`
  (`pool_sessions.py:690-695`) becomes a bounded wait on a per-session queue.
  The release at `:700-703` hands the freed slot to the next waiter. The other
  `BUSY` refusals (`:678-684`, `:719-724`) are out of scope: a reconnecting rig,
  and rigs held by another model's session.
- **Bound:** a new `Settings` field for the slot wait, beside `chat_wait_ready_s`
  (`config.py:117`). On timeout, it raises the existing `BUSY`, which becomes 503
  `pool_busy` with `Retry-After` (`completions.py:127-134`, `openai.py:49-53`).
- **Cancel on client disconnect.** Nothing watches the client on `connect`
  (§1). hub#4's `while_connected` makes a disconnect during the wait cancel it,
  and a test proves it against the real ASGI stack rather than assuming the
  server cancels the handler. A cancelled waiter leaves the queue and is never
  handed a slot.
- **Depth is already bounded.** A waiter holds one of its user's in-flight slots
  (`completions.py:226-235`). So one user queues at most
  `chat_max_concurrent_per_user` (`config.py:120`). Fewer refused retries also
  spend less of the user's rate window (`completions.py:217-225`).
- **The same queue is the drain/reload hold.** It gets a hold: admit none,
  keep waiters. hub#4 adds it as `hold()` / `resume()` (§1). A later fleet
  drain then holds requests through this queue and builds no second one. No
  drain is built here (§1: `drain` is something else). The idle sweep must not
  stop a session that has waiters. On `connect` it checks only `relays == 0`
  (`pool_sessions.py:299-310`), and hub#4 adds the waiter check (§1).
- **Tests first:** a request beyond the cap waits and is served when a relay
  ends; a timeout gives 503 `pool_busy` with `Retry-After`; a cancelled waiter
  leaks no slot; waiters are served in arrival order; a held queue admits none.
  Then the hub's own gate.

## 7. Step 4 — order of service

Follows Step 3, on the same queue. In progress (§2).

- **Weighted fair queue over one seam,** `contribution_weight(user_id) -> float`.
  It is a placeholder that returns equal weights until the hub's credits ledger
  supplies the real weight. That ledger is slice 4 of 7 on hub `connect`, and it
  is not built (#46). It owns the unit, earning, spending and balance-gated
  admission. **None of those is defined here.** The queue orders requests that
  have already been admitted.
- **Equal weights: users take turns. Decided** by the owner on 2026-10-02, as
  #46 records. With equal weights the queue is round-robin across users, with
  arrival order within a user, not strict FIFO. A weight later skews the turns
  toward users who give more. A test pins the equal-weight order.
- **Hitchhike:** the host's own requests go first. Riders are admitted only while
  their count is under the host's rider-slot cap. No cap exists yet (§1), and
  slice 6 is not started, so the queue reads the cap through a second seam that
  has no cap by default.
- **Tests:** equal weights give turns across users, in arrival order within
  each user; under saturation, unequal weights give shares within a stated
  bound of the weight ratio; the host jumps the riders; the rider cap holds.

## 8. Step 5 — e2e evidence

Several concurrent users go through the real hub and the real rig agent, using
lab PR #42's demo tooling (`lab#42:tools/demo/demo-up`, `lab#42:tools/demo/chat.py`).
The record reads, per user and per run:

- aggregate throughput;
- the wait in the queue, and the count of timeouts with their `Retry-After`;
- the share each user received against their weight;
- with Step 2 landed, the head's `-np` from its args file, as in
  `head-args-3.txt` (§1).

The evidence directory is `records/evidence/<run date>-pooled-social-e2e/`,
shaped like `lab#42:records/evidence/2026-10-02-pooled-e2e/`.

## 9. Gates, in one place

| step | passes when |
|---|---|
| 0 | each of the three questions has a quoted file:line answer in the pinned build, in the desk-read directory |
| 1 | GO / NO-GO read per §4, with the per-rung table beside it, and every row stamped with `img=` and `-np` |
| 2 | product: `make product-check` and `make guard` from the lab root. Hub: its own gate. Both are draft PRs, tests first |
| 3, 4 | hub: tests first, then the hub's own gate, with real output in the draft PR |
| 5 | the evidence directory holds the raw per-request rows, not only a summary |

## 10. Not in scope

- Solo batching, `n=` and the local-exhaustion line: #32.
- Solo work spilling to the pool when local rungs are full: not chosen
  (2026-10-02, #46).
- The credits ledger, the hitchhike slice and the fleet drain itself. Each
  plugs into a seam here, and none is built here.

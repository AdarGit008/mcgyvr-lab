# Social batching on the hub — planned 2026-10-02

**Issue #46. PLAN-ONLY. Nothing has been merged, and nothing here authorises a
launch.** Steps 1 and 5 have run as draft lab PRs, and Steps 2, 3 and 4 and
the session width are built as draft PRs. §2 gives each step's state. The
owner approved this work plan on 2026-10-02, and #46 records the decisions of
2026-10-02 and 2026-10-03. It covers many users' requests on one
pooled session, sent through the hub: the pooled sessions of path (b), giving
hardware to a pool, in #46 § Terms, which defines "solo". Batching on the
user's own network (`n=`, the local-exhaustion line) is #32. Its plan is
`records/plans/request-batching-2026-10-01.md`, and nothing in it is restated
here.

**The prediction, now measured:** serving several requests at once on a pooled
head would hide the per-token RPC round trip across rigs, so that each decode
step paid the round trip once for every slot, not once per request. Step 0 read
the mechanism in source (§3), and Step 1 measured the wall clock: it does not
(§4). Steps 3 and 4 (the wait queue and its order) went ahead of the
measurement, by owner approval. They remove the instant refusal and order the
wait even at one slot, so they do not depend on the answer.

**Citations.** Each one names its repository and commit:

| prefix | repository | ref |
|---|---|---|
| `hub:` | AdarGit008/mcgyvr-hub, branch `connect` (draft mcgyvr-hub#1) | `1d59722` (`main` is `5a85d0c`) |
| `rig:` | AdarGit008/mcgyvr, branch `mcgyvr-connect` (draft mcgyvr#564, stacked on #562) | `11415cc6` |
| `hub#4:` | AdarGit008/mcgyvr-hub, branch `pool-wait-queue` (draft mcgyvr-hub#4, base `connect`) | `d389c20` |
| `hub#5:` | AdarGit008/mcgyvr-hub, branch `pool-fair-order` (draft mcgyvr-hub#5, base `pool-wait-queue`) | `dc9d626` |
| `hub#8:` | AdarGit008/mcgyvr-hub, branch `pool-session-width` (draft mcgyvr-hub#8, base `pool-fair-order`) | `275cb5c` |
| `hub#14:` | AdarGit008/mcgyvr-hub, branch `pool-head-slots` (draft mcgyvr-hub#14, base `pool-session-width`) | `35eb821` |
| `rig#569:` | AdarGit008/mcgyvr, branch `rig-head-slots` (draft mcgyvr#569, base `fix/single-rig-session-connect`, draft mcgyvr#566) | `abccb902` |
| `lab#42:` | this repository, branch `mcgyvr-social` (draft lab PR #42, unmerged) | `cf53dc3b` |
| `lab#48:` | this repository, branch `lab/pooled-slots-desk-read` (draft lab PR #48, unmerged) | `5c1ef3bd` |
| `lab#50:` | this repository, branch `lab/pooled-slots-measure` (draft lab PR #50, base `mcgyvr-social`, unmerged) | `cd02fc40` |
| `lab#52:` | this repository, branch `lab/pooled-slots-e2e` (draft lab PR #52, base `mcgyvr-social`, unmerged) | `23c9d08d` |
| no prefix | this repository, `main` | `b242f46a` |

**"The desk read"** below means Step 0's record,
`lab#48:records/evidence/2026-10-02-pooled-slots-desk-read/README.md`. It is
cited by its sections, §Q1 to §Q5.

**"The measurement"** below means Step 1's record,
`lab#50:records/evidence/2026-10-03-pooled-slots/README.md`. It is cited by its
section headings, and its numbers are not copied here except the verdict's
margin (§4).

**"The e2e record"** below means Step 5's record,
`lab#52:records/evidence/2026-10-03-pooled-slots-e2e/README.md`. It is cited
by its section headings, and its numbers are not copied here except the
verdict's margin and the longest wait (§6, §8).

---

## 1. What exists

This is `connect` as cited. A row that hub#4 (Step 3) or hub#8 (the session
width) changes says so.

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
| Join, don't plan: a joinable session is returned whether or not it is full, the ready ones with the fewest relays first. hub#8 picks the most free seats instead, and when every session is full, the shortest queue per seat | `hub:src/mcgyvr_hub/pool_sessions.py:463-479`; `hub#8:src/mcgyvr_hub/pool_sessions.py:603`, `:1642-1645` |
| A rig is in at most one active session | `hub:src/mcgyvr_hub/models.py:371-383`, `hub:src/mcgyvr_hub/protocol.py:18` |
| `session_max_relays = 4`, a constant for every session. hub#8 removes it: each live session has a `width`, taken from `HEAD_SLOTS = 1` as it starts | `hub:src/mcgyvr_hub/config.py:74`; `hub#8:src/mcgyvr_hub/pool_sessions.py:74-80`, `:278`, `:973` |
| The full-session refusal: `SessionError(BUSY, retry_after_s=1)`, counted and released around the yield. hub#4 makes it a bounded wait first (§6) | `hub:src/mcgyvr_hub/pool_sessions.py:690-703`; `hub#4:src/mcgyvr_hub/pool_sessions.py:789-822` |
| `BUSY` maps to 503 `pool_busy`, and `retry_after_s` becomes the `Retry-After` header | `hub:src/mcgyvr_hub/completions.py:127-134`, `hub:src/mcgyvr_hub/api/openai.py:49-53` |
| Other `BUSY` refusals, which are not the full-session case: a rig is reconnecting, or the model's rigs are in another session (`_RETRY_AFTER_S = 5`) | `hub:src/mcgyvr_hub/pool_sessions.py:70`, `:678-684`, `:719-724` |
| The ready-wait is separate: up to `chat_wait_ready_s` (20 s) for a loading session, then 503 `model_loading` | `hub:src/mcgyvr_hub/completions.py:237-241`, `hub:src/mcgyvr_hub/config.py:117`, `hub:src/mcgyvr_hub/pool_sessions.py:729-757` |
| The idle sweep stops a ready session only when it has `relays == 0`. hub#4 also spares a session that has waiters | `hub:src/mcgyvr_hub/pool_sessions.py:299-310`; `hub#4:src/mcgyvr_hub/pool_sessions.py:358-371` |
| `PoolSessions.drain` waits for the hub's own background tasks. It is **not** a fleet drain, and no fleet drain exists. hub#4 adds the hold that a drain would use, `hold()` / `resume()`, and nothing calls it yet | `hub:src/mcgyvr_hub/pool_sessions.py:276-282`; `hub#4:src/mcgyvr_hub/pool_sessions.py:725-739` |
| Nothing watches the client's HTTP connection while `start` waits. hub#4 adds `_while_connected` in `api/openai.py`, on `/v1` only, which cancels the start on `http.disconnect`. The pool page's Try-it box is left as `connect` has it, because hub#2 deletes Try-it | `hub:src/mcgyvr_hub/api/openai.py:134-137`; no hit for `is_disconnected` or `http.disconnect` in `hub:src/`. `hub#4:src/mcgyvr_hub/api/openai.py:123-139`, `:157-163` |
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
With hub#8 a session admits only its width, 1 today, so the second request
already waits in the hub's queue, in hub#5's weighted turns (§7). The weight is
a placeholder of 1.0 for everyone until the credits ledger supplies it.

## 2. The plan

```text
 Step 0  desk read (llama.cpp source) ───────┐
                                             ├──► Step 1  measure ──GO──► Step 2  multi-slot head
 lab PR #42 rpc-split tooling ───────────────┘         (on product #566, hub #8)

 Step 3  wait queue (hub `pool-wait-queue`, off `connect`) ──► Step 4  order of service
                                                                  (weight seam; ledger later)

 Steps 2 + 4 ──► Step 5  e2e evidence through the real hub and rig agent
```

**Order.** Steps 0 and 3 ran first, in parallel. Step 4 followed Step 3. Step 1
needs lab PR #42's tooling. Step 2 needs Step 1's GO, which it has, and builds
on product #566 and hub #8 (§5). Step 5 reads whatever has landed by then. #32
stays separate.

**State, 2026-10-03:**

| step | state |
|---|---|
| 0 | done: the desk read, draft lab PR #48 (§3) |
| 1 | done, **GO**: the measurement, draft lab PR #50 (§4) |
| 2 | built, owner-approved on 2026-10-03: draft mcgyvr-hub#14 (`pool-head-slots`, stacked on #8) and draft mcgyvr#569 (`rig-head-slots`, stacked on #566) (§5) |
| 3 | built: draft mcgyvr-hub#4 (§6) |
| 4 | built: draft mcgyvr-hub#5, stacked on #4 (§7) |
| session width | built: draft mcgyvr-hub#8, stacked on #5. It is the hub half of Step 2's "caps follow slots", taken ahead by the owner's decision of 2026-10-03 (§5) |
| 5 | done: the e2e record, draft lab PR #52, through hub#14 and rig#569 (§8) |

**Overlap.** The hub's draft mcgyvr-hub#7 (`pool-fleets`, standing units, slice
2a of the hub plan) is based on #8 (`pool-session-width`, as of 2026-10-03),
which gives each standing unit a width; its merge order is in §10. Hitchhike
6b (slot advertising, another session's hub slice, #46
§ Terms) reuses Step 2's `Slots` type on a unit advertisement message and rides
the same schema change (§5). **Per-card allocation** (the other session's
decision of 2026-10-03, built by another session as a hub slice): a unit takes
the cards its layers and `slots × ctx` of KV need, no two units share a card,
and one unit may span cards and rigs. It must keep hub#14's invariants, a
head-rig card last in device order and KV charged per card, the RPC workers'
included (§5), and it comes after 6b (§10).

**Open, 2026-10-03:**

- Tests that fail intermittently, already on `connect`: the member-state tests
  in `test_pool_access.py` (`hub:tests/test_pool_access.py:280`, `:296`), and
  `test_relay.py::test_the_byte_cap_ends_the_allocation`
  (`hub:tests/test_relay.py:220`). hub#4, #5 and #8 change neither test file.
- The desk read's §Q5 cell, the prompt-cache save read back over RPC, was left
  out of Step 1. It is now cell 7 in §4, optional.

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

**Done: GO** (§4 Result, at the end of this section).

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
7. **Prompt-cache save read-back, optional.** S2 with `--cache-ram 0` against
   the default, read at C = 4, where the requests past its two slots make the
   slots turn over. Saving an idle slot reads its KV back from every device,
   the RPC worker included, and its cost per slot switch is open (§Q5). The
   flag goes in the cell's extra, which the driver passes verbatim
   (`mgpu_sweep.py:28-29`).

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

### Result: done, GO (2026-10-03)

The record is the measurement (draft lab PR #50), at
`lab#50:records/evidence/2026-10-03-pooled-slots/`.

- **Verdict: GO.** At C = 2 and C = 4, every invocation of S*C* beat S1 by more
  than the tie bar. The worst margin was +18.7% against a 0.9% bar at C = 2,
  and +67.0% against a 5.1% bar at C = 4 (the measurement's "Go / no-go for
  step 2" and "Tie bar" sections).
- **The open prediction: no.** Batching does not hide the RPC round trip, and
  the logits read-back grows with busy slots (the measurement's "The open
  prediction" section, and its desk-read cell 6).
- **Deviations** from this section are listed in the measurement's
  "Deviations" section, and what it leaves unverified in its "Not verified"
  section.

## 5. Step 2 — multi-slot head (built)

**Built, owner-approved on 2026-10-03,** after Step 1's GO (§4), as two draft
PRs. Each one's description holds its RED and GREEN runs, its gate output and
what it leaves unverified:

- hub: draft mcgyvr-hub#14, `pool-head-slots` @ `35eb821`, base
  `pool-session-width` (draft mcgyvr-hub#8). Step 5 ran `76cd212`; the later
  commits only raise the slot-wait default (§6);
- product: draft mcgyvr#569, `rig-head-slots` @ `abccb902`, base
  `fix/single-rig-session-connect` (draft mcgyvr#566).

Neither PR ran on a rig. Step 5 ran both on rigs (§8).

The product half travels as `okf/must-read/the-split.md` says: a product PR from
`product/`, then `make product-check` and `make guard`.

```text
hub planner ── fits slots × ctx of KV on every device, RPC worker included;
     │         target 4, then 2, then 1 (a setting) ──► Plan.slots
     │         devices ordered with a head-rig card last (output layer off the worker)
     ▼
HeadStartBody.slots: Slots (≤ 16, default 1; > 1 only with "head_slots")
     │                                 ──► rig: -np slots, -c slots × ctx, never -kvu
     ├─► hub session width = slots         (HEAD_SLOTS removed; it was 1, hub#8)
     └─► rig relay cap per head = slots    (an overall rig bound stays as a safety net)
```

**The contract, owner-approved on 2026-10-03:**

- **Wire.** `HeadStartBody.slots` has a reusable type, `Slots`: at most 16,
  default 1. The field is additive under `v = 1` (`protocol.py:148-149`), so
  there is no protocol version bump. An older agent drops it silently and
  launches `-np 1` (`sessionwire.py:496-550`, `pooled.py:656-657`). So the hub
  sends `slots > 1` only to an agent that lists the feature tag `"head_slots"`
  in `capabilities.features` (`protocol.py:55-57`). Otherwise the hub would
  admit N relays into one slot. Hitchhike 6b reuses `Slots` (§2, Overlap).
  **Built:** `hub#14:src/mcgyvr_hub/protocol.py:214`, `:283-285`, `:692`; the
  rig reads the field in one helper (`rig#569:src/mcgyvr/rig/sessionwire.py:51-52`,
  `:400-404`).
- **`ctx` is per slot: split KV, never `-kvu`. Decided** by the owner on
  2026-10-03, as #46 records. The rig runs `-np slots -c slots × ctx`. An
  explicit `-np` gives each slot its own window of `-c / slots` (the desk read
  §Q1, confirmed by the measurement's desk-read cell 1). `-kvu` would keep the
  total at `ctx` but share it, and a full shared pool fails every running
  request together (§Q1, confirmed by cell 2). **Built:**
  `rig#569:src/mcgyvr/sandbox/pooled.py:665-668`.
- **Planner. Decided** 2026-10-03. It fits `slots × ctx` of KV per block on
  every device the layer sits on, the RPC worker included (the desk read §Q3).
  So a worker that fits one slot's KV may not fit four. It tries a target of 4
  slots, then 2, then 1, and the target is a hub setting. It recalibrates the
  compute-buffer term against Step 1's `CONFIG` buffer readings, as the
  existing calibration cases do (`planner.py:84-90`). That term does not follow
  `-np` monotonically (the measurement's "Context ceiling per slot" section).
  The new count gets a name other than `_slots` (`planner.py:355`).
  **Built** in hub#14 as `PlannerParams.target_slots`, default 4
  (`hub#14:src/mcgyvr_hub/planner.py:142`), and `Plan.slots`.
- **The slot count is a per-unit input to planning. Decided** by the owner on
  2026-10-03. `plan(..., target_slots=, exact_slots=)` takes it per unit: a
  target is tried, then halved down to 1, and `exact_slots` takes that count
  or no plan. With no target, the default tries 4, then 2, then 1
  (`hub#14:src/mcgyvr_hub/planner.py:822-906`; `PoolSessions._plan_on`,
  `hub#14:src/mcgyvr_hub/pool_sessions.py:548-579`). Choosing each unit's slots
  from usage belongs to the other session's fleet logic (§2, Overlap), and
  nothing in hub#14 decides it (hub#14's description, "A slot target per
  unit").
- **Output layer off the RPC worker. Decided** by the owner on 2026-10-03: the
  hub orders the devices so that a head-rig card is last, which keeps the
  output layer off the RPC worker (the measurement's desk-read cell 6).
  **Built** in hub#14 with one fallback: only when the blocks fit no other way
  does the head go first and a worker's card last
  (`hub#14:src/mcgyvr_hub/planner.py:60-68`, `:421-448`).
- **Width = slots. Decided** 2026-10-03. The hub's half of "caps follow slots"
  was built ahead of this step, by the owner's decision of 2026-10-03 (#46): the
  hub admits each session's own width, and the mcgyvr client is unchanged.
  hub#8 removes `session_max_relays` and admits `relays < width`, with the
  width taken from the one constant `HEAD_SLOTS = 1`
  (`hub#8:src/mcgyvr_hub/pool_sessions.py:74-80`, `:857`, `:886`, `:973`).
  Step 2 removes `HEAD_SLOTS`, and a session's width is the slots its head was
  launched with. **Built:** `width=plan.slots`
  (`hub#14:src/mcgyvr_hub/pool_sessions.py:952-983`).
- **Rig cap per head = slots. Decided** 2026-10-03. The rig caps relays per
  head session at that session's slots, and keeps an overall rig bound as a
  safety net. Today its only cap is the per-agent `MAX_ACTIVE`
  (`relay.py:43-44`, `verbs.py:213`). **Resolved:** this plan had both "the
  rig's cap becomes the slot count" and "`MAX_ACTIVE` stays the backstop",
  with no hub check of a width against `MAX_ACTIVE`
  (`hub#8:src/mcgyvr_hub/pool_sessions.py:74-80`). Both hold, at different
  scopes: the per-head cap is the slots, and the overall bound is the safety
  net. The per-head cap must equal the slot count exactly. The engine holds any
  request past its slots in its own FIFO, with no bound and no timeout (the
  desk read §Q2), and the hub's order of service (Step 4) cannot reach it
  there. Step 2 keeps the hub's width and the rig's cap equal by carrying both
  from one field. **Built** in rig#569: a relay past the head's slots is
  answered `busy`, and the rig-wide bound `MAX_ACTIVE` is now `MAX_SLOTS`
  (16), not 4 (`rig#569:src/mcgyvr/rig/relay.py:49-52`, `:136-147`). So a
  one-slot head now takes one relay at a time, not 4, which constrains when
  rig#569 may deploy (§10).
- **Resolved earlier:** the plan said that hub#4's cap of 4 over a one-slot
  head meant Step 4's order reached only the requests past the fourth relay.
  hub#8 makes the cap the width, 1, which equals the head's `-np 1`, so no
  request waits in the engine and every request past the first is ordered by
  the hub.
- **Silence while held.** A request the engine holds sends no byte until its
  task starts. The desk read §Q2 said its first token, and the measurement's
  desk-read cell 3 corrects that. The relay's and client's idle timeouts must
  allow for that silence. With caps equal to slots, the wait moves to the hub,
  where `chat_wait_slot_s` bounds it (§6).
- **Left open:** whether the hub should name slot ids to keep busy slots
  consecutive (the measurement's desk-read cell 4). Today the engine picks the
  slot (§Q4).

## 6. Step 3 — wait queue (owner-approved ahead of the measurement)

Hub branch `pool-wait-queue` off `connect`, as a draft PR with base `connect`.

**Built:** draft mcgyvr-hub#4. Its new setting, `chat_wait_slot_s`, defaults to
30 s (`hub#4:src/mcgyvr_hub/config.py:118`). **Owner decision, 2026-10-03:**
raise that default to 180 s, because Step 5 measured hub queue waits up to
141 s (the e2e record, "Throughput: slots 4 vs 1 through the hub" and "The
wait queue"). **Built** in hub#14 (`hub#14:src/mcgyvr_hub/config.py:117`),
whose description gives its RED, GREEN and gate. The ordering seam is
`_Queue._next()` (`hub#4:src/mcgyvr_hub/pool_sessions.py:190-193`), which
Step 4 fills (§7). Its cap is `session_max_relays` until hub#8 makes it the
session's width (§5).

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
  (§1). hub#4's `_while_connected`, on `/v1` only, makes a disconnect during
  the wait cancel it, and a test proves it against the real ASGI stack rather
  than assuming the server cancels the handler. A cancelled waiter leaves the
  queue and is never handed a slot. Try-it is not wrapped, because hub#2
  deletes it (§1).
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

Follows Step 3, on the same queue. **Built:** draft mcgyvr-hub#5, which fills
`_Queue._next()`.

- **Weighted fair queue over one seam,** `contribution_weight(user_id) -> float`
  (`hub#5:src/mcgyvr_hub/pool_sessions.py:156-168`), injected as
  `PoolSessions(..., weight=)` (`:338`, `:344`). It is a placeholder that
  returns 1.0 for everyone until the hub's credits ledger supplies the real
  weight. That ledger is slice 4 of 7 on hub `connect`, and it is not built
  (#46). It owns the unit, earning, spending and balance-gated admission.
  **None of those is defined here.** The queue orders requests that have
  already been admitted.
- **Scheme: start-time fair queueing,** one unit of cost per relay, which gives
  the same order as stride scheduling
  (`hub#5:src/mcgyvr_hub/pool_sessions.py:181-204`). A turn is charged when it
  is given, not on arrival (`:236-240`, `:250`, `:848`), so a request that
  gives up costs nothing. There are no banked turns: a user who was away comes
  back at the queue's virtual time (`:225-226`).
- **Equal weights: users take turns. Decided** by the owner on 2026-10-02, as
  #46 records. With equal weights the queue is round-robin across users, with
  arrival order within a user, not strict FIFO. A test pins the equal-weight
  order.
- **Priority by what you give means weighted turns. Decided** by the owner on
  2026-10-03, as #46 records: users who give more get more turns, not strict
  priority over the others. A user of weight w gets about w turns to another's
  one, and no weight above 0 starves
  (`hub#5:src/mcgyvr_hub/pool_sessions.py:188-204`).
- **Hitchhike: no rider ordering was built,** because hitchhike has no serving
  path today. `access.may_hitchhike` has no caller in `hub:src/`, and
  `may_split` refuses a hitchhike rig to anyone but its owner
  (`hub:src/mcgyvr_hub/access.py:110-119`, `:133`). `_next()`'s docstring says
  where host-first order and the rider-slot cap plug in once riders can join
  (`hub#5:src/mcgyvr_hub/pool_sessions.py:228-234`).
- **Tests:** hub#5's description lists them, with the red run and the
  mutation checks.

## 8. Step 5 — e2e evidence (done)

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

### Result: done (2026-10-03)

The record is the e2e record (draft lab PR #52), run on hub#14 and rig#569.
Its directory is `lab#52:records/evidence/2026-10-03-pooled-slots-e2e/`, not
the `…-pooled-social-e2e` named above (its "Deviations", item 2).

- **Verdict:** slots 4 beat slots 1 through the real hub and rig agent in every
  invocation. Worst slots-4 invocation against best slots-1: +81.4% at C = 4
  against a 4.2% tie bar, and +97.3% at C = 8 against a 1.0% bar ("Throughput:
  slots 4 vs 1 through the hub").
- **Queue:** extras waited and were served inside `chat_wait_slot_s`; past it,
  503 `pool_busy` with `Retry-After`; a client that hung up while queued left
  the queue, and the next waiter took the seat ("The wait queue").
- **Order of service:** with equal weights, users took alternating turns, not
  arrival order. Weighted turns were not exercised with real weights ("Order of
  service").
- **Rig cap:** the head agent answered no `busy` and no client got a 502; the
  hub admitted at most the width ("Rig cap: no `busy` from the head").
- **Deviations** from this section are in the e2e record's "Deviations"
  section, and what it leaves unverified in its "Not verified" section.

## 9. Gates, in one place

| step | passes when |
|---|---|
| 0 | each of the three questions has a quoted file:line answer in the pinned build, in the desk-read directory |
| 1 | GO / NO-GO read per §4, with the per-rung table beside it, and every row stamped with `img=` and `-np` |
| 2 | product: `make product-check` and `make guard` from the lab root. Hub: its own gate. Both are draft PRs, tests first |
| 3, 4 | hub: tests first, then the hub's own gate, with real output in the draft PR |
| 5 | the evidence directory holds the raw per-request rows, not only a summary |

## 10. Merge order

**Agreed with the other session on 2026-10-03, pending the owner's OK.**
Nothing in it is merged. `A ← B` means B merges after A. This is the order of
merging, not each PR's GitHub base, and several bases differ from it.

| repo | order |
|---|---|
| hub | `connect` #1 ← #6 ← #4 ← #5 ← #8 ← #14 ← #7 ← #9 ← #10 ← #11 ← #12 ← #13 ← #16 ← #15. Separately, #3 → `main` |
| product | #562 ← #565 ← #564 ← #566 ← #569 ← #568 ← #570 ← #571 |
| lab | #42 after product #562, then #49, #51, #50 and #52 on `mcgyvr-social`. #47 and #48 on `main` at any time |

- **hub:** #6 is the single-rig port, which #7 needs. #12 is hitchhike 6a. #13
  (`web-feed`) contains web-home #2, which can close or merge into `connect`
  first. #16 is `fix/live-b`. #15 is the hitchhike 6b relay; it contains #14,
  and will contain #16 after its next push.
- **product:** #565 is the single-rig fix. #568 is the relief rungs. #568
  already contains #561 (merged to product `main` 2026-10-02); #562's branch
  (`mcgyvr-social`) is behind `main` and must take `main` before merging. #570
  is the agent flush. #571 is the 6b serve; it contains #569, and will contain
  #570.
- **lab:** #49 is live-a and #51 is live-b.

**Constraints:**

- rig#569 never deploys ahead of hub#8. At slots = 1 the rig now takes 1 relay
  per head, not 4 (§5), so a hub that still admits 4 per session would get
  `busy` for the 2nd to 4th.
- The product's schema pin (`rig#569:tests/rig_schema.py:41-45`) must equal the
  final hub schema once both hub#14 and hub#15 have landed. Re-check it then.
- Product #562 (`mcgyvr-social`) takes product `main` before it merges (the
  product note above).
- Lab #42 merges after product #562.
- Per-card allocation comes after 6b (§2, Overlap).

## 11. Not in scope

- Batching on the user's own network, `n=` and the local-exhaustion line: #32
  (#46 § Terms).
- Hitchhike spill, path (a) in #46 § Terms: hub slice 6. This plan does not
  build it. The 2026-10-02 "not chosen" meant only that, and was not a ruling
  against hitchhike spill (owner, 2026-10-03, #46 § Not in scope).
- The credits ledger, the hitchhike slice and the fleet drain itself. Each
  plugs into a seam here, and none is built here.

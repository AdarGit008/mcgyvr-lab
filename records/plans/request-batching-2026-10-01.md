# Request batching and the local-exhaustion line — planned 2026-10-01

**Issue #32. PLAN-ONLY. Nothing has been launched, and nothing here authorises a
launch.** The owner chose a proposal and measurement plan, with no product code.

**Prediction: there is nothing to build.** Width already batches on the server.
The pinned vLLM leaves automatic prefix caching at its engine default, and with it
the server reads a shared prompt once. `n=` can cover only the sampled draws, and
it costs per-draw accounting the product relies on. The run below exists to
falsify that prediction cheaply. Gate 0 below is a desk read that may make the
run unnecessary.

Paths under `src/` are the product's (`product/src/...`), at the product
commit `product/` points at.

---

## 1. What exists

```text
contract ─► drive.fetch(draw) × draws ─► run_batch (one job per draw)
                │                            │
                │ temperature: draw 0 = 0.0  │ Capacity.hold: one slot per draw
                │ draws 1..N-1 = breadth.temp│
                ▼                            ▼
        one POST /v1/chat/completions per draw ─► server batches them
        (vLLM continuous batching, --max-num-seqs = width;
         llama.cpp --parallel = width)
                │
                ▼
        telemetry.observe: one journal row per draw
```

| fact | where |
|---|---|
| Draws are one job each, run concurrently inside the source's width | `src/mcgyvr/drive.py:834-837` (`run_batch`), `src/mcgyvr/capacity.py:1380-1434` |
| Each draw holds one slot; each slot is one `flock`ed file per source | `src/mcgyvr/capacity.py:1007` (`hold`), `:1116-1126` |
| Draw 0 is greedy and draws 1..N-1 sample at `breadth.temperature` | `src/mcgyvr/drive.py:958-969` (`_temperature_of`) |
| `best_of` gates the fetched replies one at a time, after every fetch has returned | `src/mcgyvr/drive.py:850-870`, `src/mcgyvr/consensus.py:200` |
| One request per dispatch to `/v1/chat/completions`; the body never carries `n`; only `choices[0]` is read | `src/mcgyvr/runner.py:547`, `:550-577`, `:579-613` |
| One journal row per draw, carrying `temperature`, `input_tokens`, `output_tokens`, `stop_reason`, `reply_sha256`, `in_flight` | `src/mcgyvr/telemetry.py:184`, `:315-340`, `:345-385`, `:460-488`; draw index in `attempt_id`, `src/mcgyvr/drive.py:423-443` |
| Token counts come from the server's `usage`; there is no tokenizer in `dependencies` (`tokenizers` sits only in the `measure` group) | `src/mcgyvr/runner.py:608-609`; `product/pyproject.toml` `dependencies`, `[dependency-groups].measure` |
| vLLM launch: `--max-num-seqs` = width, `--max-model-len`, `--kv-cache-dtype`, plus `serve_args`. No prefix-caching flag either way, so the pinned engine's default applies | `src/mcgyvr/serving/__init__.py:786-800`; image `src/mcgyvr/emit.py:64` |
| llama.cpp launch: `--parallel` = width, `-b`/`-ub` = `DEFAULT_UBATCH`. No `--cache-reuse`. The runner sends no `cache_prompt`, so the server default applies | `src/mcgyvr/serving/__init__.py:74`, `:824-835` |
| `ubatch` sizes a launch; it does not merge requests | `src/mcgyvr/serving/vramfit.py`, `src/mcgyvr/serving/__init__.py:74` |
| The server's own in-flight count is read around every dispatch: vLLM `/metrics` running + waiting, llama.cpp `/slots` | `src/mcgyvr/runner.py:772-784`, `:861`, `:872-892` |
| Slot pressure is reported, never acted on: `in_flight`, `load`, `usage()` (`peak`, `waited_seconds`, `saturated`), `concurrency()` | `src/mcgyvr/capacity.py:823-846`, `:979-1000`, `:400`, `:429` |
| The one capacity-driven cross-tier move: `fanout: idle` takes the cheapest rung with `load < width` at or above the floor. This can be a priced API rung | `src/mcgyvr/escalate.py:20-32`, `:765-778` |
| The pre-API seam: `wake_hook` runs when the next family is the API | `src/mcgyvr/escalate.py:1004`, `:1205-1206`, `:1337`; `src/mcgyvr/fleet_manager.py:140-190` |

So request batching already happens on the server. The client sends N concurrent
requests and the engine schedules them in one batch.

## 2. What `n=` or a batch endpoint could add, and what it costs

The one possible gain is reading a shared prompt once (prefill reuse). Width
already gives decode batching. vLLM's automatic prefix caching gives prefill reuse
across the N requests whenever the engine has it on, and the product's launch
leaves it at the engine default. Gate 0 reads what that default is.

| axis | N requests (today) | one `n=` request |
|---|---|---|
| **Throughput ceiling** | `--max-num-seqs` sequences | The same. Each choice is a sequence in the engine's batch, so `n` does not raise the ceiling |
| **Latency** | Each draw returns when it finishes | All choices return together. Group latency is the slowest choice. No loss today, because `best_of` waits for every fetch anyway (`drive.py:850-870`). One transport failure loses every draw, and a retry re-runs them all |
| **Per-draw temperature** | Draw 0 at 0.0, the rest at `breadth.temperature` | One request has one temperature. Draw 0 stays a separate request, so `n` covers only draws 1..N-1 (`n = N-1`) |
| **Journal** | One row per draw, each with its own `output_tokens`, `stop_reason`, latency and decode rate | `usage` is per request: the prompt is counted once and completion tokens are summed over the choices. A per-draw row loses its own `output_tokens` and decode rate unless something counts them |
| **No tokenizer** | Server `usage` suffices | Counting per-choice tokens client-side needs a tokenizer. That is forbidden in `dependencies`. The only alternative is an estimate, which must say it is one (`okf/must-read/the-split.md`) |
| **Capacity** | One `hold` = one request = one server sequence | One request would hold N-1 server sequences. `hold` would have to take N-1 slots, or the width bound stops meaning what the server enforces |
| **`in_flight`** | `busy + 1` per dispatch (`runner.py:772-784`) | `+1` under-counts by N-2. The field's meaning changes |
| **llama.cpp** | Works | Unverified on the pinned build (Gate 0). If it refuses `n != 1`, the product carries two dispatch paths |
| **Batch file API** (`/v1/batch`, offline `run_batch`) | — | Asynchronous and job-shaped. It does not fit an interactive ladder dispatch. Out of scope |

## 3. "Local throughput exhausted": the line before the API

**Proposed criterion. It is expressed in what the product already reads, and no new
signal is needed.** For the contract's floor family and every local family above it,
up to the API:

- **in-process:** `Capacity.load(source, rung) >= Capacity.limit(source, rung)`.
  This is the predicate `Ascent.next_free_rung` already uses (`escalate.py:775`).
- **cross-process (closes the gap `route.py:296-305` names):** the server's own
  `busy`, read the way `runner._status` reads it, is at or above the width.
  `busy` is vLLM `/metrics` running + waiting. On llama.cpp it is the `/slots`
  entries with `is_processing` set. A waiting count above zero means the
  scheduler is queueing.

Local is exhausted only when every such rung meets both. Batching changes neither
term, because `n=` takes as many engine sequences as N requests do. Width is the
whole local throughput lever. The measurement's other job (§4, check W) is to
confirm that the declared width sits at the knee, so that `load >= width` really
means no throughput is left. If it does not, the finding is a width setting, not
batching.

**Relation to #33.** In the #33 build being done in parallel, Jev watches this
same pressure at the same seam (`escalate.py:1205`). This criterion is the
*capacity* half: is there a free awake local slot? #33's wake judgment is the
*capability and dormancy* half: should a sleeping, bigger local rung be woken
instead of the API? The order at the seam: (1) if any awake local rung is not
exhausted, it is not time for the API; (2) only then does #33 decide on a wake.
The predicate is defined **once**, in `Capacity`, beside the slot files it reads.
Jev and `next_free_rung` both call it, and neither restates it
(`okf/must-read/the-split.md`; single source of truth).

## 4. Measurement plan

**Rules it obeys:** `okf/must-read/reading-results.md`, `okf/must-read/touching-engine.md`.
Every figure is said about a config tag, never about a rig (`okf/must-read/always.md`).

### Gate 0: desk read, no rig

1. In the image `src/mcgyvr/emit.py` pins, read whether automatic prefix
   caching is on by default, and how `n > 1` is executed. Either the choices are
   fanned out as child requests over the prefix cache, or they share one prefill
   by construction.
2. In the llama.cpp build the product serves, read whether the chat endpoint
   accepts `n != 1`, and whether one slot's cached prompt can serve another slot.

**If (1) shows `n` is a fan-out over the prefix cache with prefix caching on by
default, then arm C equals arm B by construction.** Record that, and the owner
may close #32 as nothing to build without rig time. If (2) shows no `n` and no
cross-slot reuse, there is no llama.cpp arm to run, and that is recorded, not
measured.

### Instrument: extend `tools/runs/drivers/vllm_sweep.py`

Use the door-run driver, not `tools/serving/concurrency_sweep.py`. The door-run
driver already carries the door stamps, `WORKLOAD_DIGEST`, the warm-up refusal,
the `WIDTH` readback against the KV pool, `ptok`/`otok` per row and `early_stop`.
Additions:

- **Same-prompt mode** (a cell flag): each level draws **one** `workload.mkprompt()`
  and sends it N times. Draw 0 runs at temperature 0, draws 1..N-1 at one fixed
  sampled temperature. `workload.py` is untouched, so the digest does not move.
  Every arm in this mode consumes draws identically.
- **`n` mode** (a cell flag): the draw-0 request, plus one request with `n = N-1`
  at the sampled temperature, sent together.
- **Fixed output length:** `ignore_eos` + `min_tokens` = `max_tokens`, so every
  choice generates exactly the cap. Read `finish_reason` and `usage` on every
  reply. A level where any choice's tokens differ from the cap is refused. This is
  a throughput instrument, and no row from it is read as capability.
- **Prefill evidence from the engine:** read vLLM's prefix-cache query and hit
  counters and the TTFT histogram from `/metrics` before and after each level.
  The driver's own `prefill=` column divides by the same wall clock as decode and
  is not a measurement.
- **Per-draw normalisation:** report `ptok` and `otok` per draw, and aggregate
  tok/s over draws, so an `n=` row and an N-request row are comparable.
- **Repeats:** each level runs `r` times inside the cell, and the first is
  discarded. The driver's warm-up request uses a prompt that no measured level
  uses, so it cannot seed the cache in one arm's favour.

Prefix caching on/off needs no code. It goes in the cell's existing `extra`
field (`--enable-prefix-caching` or `--no-enable-prefix-caching`). Both arms spell
the flag explicitly, rather than relying on the default.

### Arms: one checkpoint, one vLLM config tag, one backend, one card

| arm | requests per level | prefix caching |
|---|---|---|
| **A** width-only | N | off |
| **B** width + prefix cache (what the product runs today, if Gate 0 confirms the default) | N | on |
| **C** `n=` | 1 + one `n=N-1` | on |
| **C0** (mechanism only) | 1 + one `n=N-1` | off |
| **Null** | B again | on |

- **Levels:** N on a ladder up to the cell's `--max-num-seqs`, plus one rung above
  it to show queueing. `--max-num-seqs` is set to the top of the ladder
  (`okf/config/vllm.md`), and the engine's maximum-concurrency line is read on
  every cell.
- **One cell per driver invocation.** Arms are interleaved across invocations
  (A, B, C, C0, Null, then again), never run in blocks
  (`okf/must-read/touching-engine.md`).
- **Comparable rows only:** a ratio is quoted only between rows whose per-draw
  `ptok` and `otok` match.
- **Tie bar:** priced from the Null replicates of B for this field (per-draw
  aggregate tok/s at each width), in the vLLM class. The `warm_decode_class_pct`
  and `prefill_class_pct` bars in `tools/runs/derived.json` judge a different field,
  and are not borrowed. A llama.cpp arm, if Gate 0 leaves one, prices its own null
  in its own class.
- **Check W (the knee):** in arm B, compare aggregate at the top rung with the rung
  below. If the gap is above the tie bar, the declared width is not the knee, and
  `load >= width` under-states what is left locally.

### Go / no-go

Read at each width that every arm ran, never as one number:

1. **Is the prompt already read once?** B's prefix-cache hit delta per level
   accounts for the shared prompt of draws 1..N-1. If it does, B already delivers
   the only gain `n=` could offer.
2. **GO on `n=`** only if C beats B on per-draw aggregate tok/s by more than the
   tie bar, at some width where both ran, in every replicate. The gain must also
   be worth §2's costs: the split draw 0, per-draw journal rows without a
   tokenizer, the N-1-slot hold, the `in_flight` semantics, and a llama.cpp
   fallback path.
3. **Otherwise NO-GO: nothing to build.** #32 closes on this record. C0 against
   A says only whether the engine shares prefill under `n` without the cache.
   That is a mechanism note, not a reason to build.
4. **Escalation criterion:** §3 is adopted either way. It needs no batching. The
   only product change it implies is moving the predicate into `Capacity` with the
   server read, and that change is shared with #33.

## Open questions

- **Owner of the shared predicate:** does §3's predicate land in #33's PR or in a
  follow-up to this one? The plan assumes it is defined once, in whichever lands
  first.
- **Multi-contract load:** should the levels also mix concurrent contracts (several
  prompts × N draws)? Prefill contends with decode only there. The plan keeps one
  prompt per level, so arms stay comparable on the workload digest.
- **Skipping the run:** if Gate 0 shows `n` is a fan-out over a default-on prefix
  cache, may the owner close #32 without running it? The plan leaves that to the
  owner.

# Replacing the API orchestrator with a local Jev-like model + a local chat agent

Design only. Nothing here is implemented, and no line of `product/` changes on
the branch that carries this file. Code lives in the `product` submodule
(`AdarGit008/mcgyvr`, HEAD 4214aea7); the Jev plays exist only as unmerged
worktrees under `/tmp/mcgyvr-play-*`.

## The owner's rulings (locked; this design does not revisit them)

1. **The API orchestrator is replaced by the combination of two local models**:
   a local *Jev-like* model (typed, calibrated decisions) and a local *chat*
   model (the conversational agent). No hosted/API model in the path.
2. **The conversational agent is backend-agnostic.** It knows nothing of the
   fleet, ladder, or catalog. It passes `prompt` + `repo`, invokes the script,
   and acts on results. It never reasons about decomposition granularity.
3. **The orchestrator role (decompose → dispatch) is done almost exclusively by
   the Jev-like model.** The conversational agent does the rest of the bounded
   loop: prompt → clarify → invoke → manage outputs → commit.
4. **The local tier and the API tier are gated identically.** No special-casing
   of the Jev+chat orchestrator; the hybrid falls back to the API tier only for
   quality, judged by the same gate.
5. **Decomposition is: deterministic enumerator proposes a few candidate splits
   → Jev `Choice` selects one → per-unit `ClassifierProposer` (type/target/
   symbol) → Jev `Noul` terminates.** No LLM breaks the prompt into units; Jev
   selects among pre-enumerated splits and never invents a unit.
6. **"Granular enough" means "will the worker succeed", and is ladder-agnostic.**
   Jev's decision state is `{request, candidate units}` only — no vocabulary,
   no ladder, no capacity. Servability is deterministic (loader +
   `max_input_tokens`); capacity is escalation's job.
7. **Split before escalate, always.** Too-coarse / failed → split finer (down to
   file/symbol granularity) → retry, to a capped depth; only when splitting is
   exhausted → escalate up the ladder.

## 1. Architecture (three layers)

```
User ──▶ [CONVERSATIONAL AGENT]        local chat model, large context, tools
              │  backend-agnostic: prompt+repo in, acts on results out
              ▼
        [DETERMINISTIC PIPELINE]        mcgyvr delegate/run: dispatch · gate · commit
              │  calls the Jev model at the typed decision seams
              ▼
        [JEV-LIKE MODEL]                decompose (select split · type/target/symbol)
                                        · granularity Noul · verify · floor · difficulty
```

The Jev-like model is a decision *component the pipeline calls* — it never sees
the user, never commits, never holds the repo. Its answers are typed
(`Choice`/`Noul`/`Score`) over single-token logprobs, never prose
(`decision.py`).

## 2. The decomposition loop

```
prompt+repo ──▶ resolver: shortlist + deps + owners         (deterministic, no model)
                 ▼
        enumerator: 2-4 candidate splits                    (deterministic, NEW component)
                 ▼
        Jev Choice: pick the split          ◀── confidence < MIN_CONFIDENCE → escalate/agent
                 ▼
        per unit: Jev Choice ×3 (type/target/symbol)        (ClassifierProposer, play-proposer)
                 ▼
        Jev Noul: "granular enough to succeed?"  ── no ──▶ re-split finer (capped depth)
                 │ yes
                 ▼
        deterministic: load · gate · dispatch · commit      (servability + escalation here)
```

Split-axes for the enumerator are structural only: rank, dependency cluster,
owner/language. A semantic split inside one symbol is below the catalog's
file/symbol granularity and out of scope; that is the one place a free-text
suggestor would re-enter, and it does not.

## 3. Model slots

- **A — conversational agent** (the hard, open slot): a capable local chat model
  with large context + tool use. Candidates to measure: deepseek-coder-v2-16b,
  Qwen2.5-Coder-14B/32B, Qwen3-30B-A3B. Eval axis is agentic/tool-use
  (BFCL-style) + long-context, *not* decision accuracy.
- **B — Jev-like decider** (the settled-ish slot): the open Jev-shaped
  reproductions. Shortlist to benchmark across arch × context:
  `autotrust/JEV-9B` and `JEV-27B` (decoder BoE, KL≈0.019/0.017 to hosted Jev),
  `com-kotobalabs/open-jev-deberta-v3-large` (encoder, 512 ctx),
  `ZefanCai/Open-Jev-9B`, `alibiserikbay/JevK5`, `samatv256/mini-Jev`,
  `chaoliangUNSW/Jev-Style-0.8B-Decision-v3`, `TokenRhythm/NeoHorse-Jev-4B`,
  plus a no-finetune control (deepseek-coder-v2-16b in raw logprob mode).
  Reference bar (hosted Jev 1.13, decisioneval.dev): acc 0.740, ECE 0.045.

## 4. Known state / gaps (all verified against code)

- `decision.py` (the Jev primitive) and the five plays are **not on product
  main** — they live only on `/tmp/mcgyvr-play-*` worktrees. Merging
  `decision.py` is the prerequisite for everything.
- The free-text orchestrator prompt already instructs "propose the **units of
  work**" and accepts a JSON array with `deps`/`allow`/`forbid`
  (`delegate.py:build_prompt`, `_reply_format`); `decompose`
  (`orchestrator/decompose.py:230`) consumes N proposals in one shot.
  `ClassifierProposer` (play-proposer) emits exactly one proposal, `allow` =
  target, no `deps` — multi-unit is its documented gap.
- The **enumerator is a new component**; nothing today partitions the shortlist
  into candidate splits.
- The worker sees two messages only: a ≤2 KiB language bundle (system) + the
  rendered `contract.worker_view()` (user) — `TASK`/`TARGET`/`CURRENT CONTENT`/
  `INTERFACE`/`DEPENDENCIES`/`STOP CONDITIONS`/`OUTPUT`. Orchestrator-only
  fields (`risk`, `acceptance`, `scope`) never reach it (`worker/prompt.py`).
- Live-fleet logprobs support (vLLM + llama-server) is **assumed, not probed**;
  `decision.classify` needs `logprobs`/`top_logprobs`/`allowed_token_ids`-style
  constraint. Must be live-probed before relying on it.
- `Config.is_local_only` checks ladder units only, not role units — a "no API"
  proof would silently pass with a hosted orchestrator/verifier.

## 5. Implementation sequence (driven by `wf`, RED → GREEN)

1. Live-probe logprobs on `srv1:8080` / `srv2:8001/8002` with the `classify`
   payload (the gating unknown).
2. Merge `decision.py` (Phase 0) into product main, then the five plays.
3. Add the deterministic enumerator (candidate splits) + the split-select
   `Choice` + the granularity `Noul`, wired into `decompose`.
4. Bind `orchestrator.unit`/`orchestrator.model` and `verifier.unit` to local
   units; extend `is_local_only` to cover roles.
5. Calibrate `MIN_CONFIDENCE` + the granularity/regression thresholds against
   journaled runs; A/B local vs API orchestrator through the same gate.

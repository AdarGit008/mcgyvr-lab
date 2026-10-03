# jev-mcorch — the local agent run — planned 2026-10-03

**PLAN, LOCKED FOR OWNER APPROVAL. Nothing below the pilots has been launched.**
Pilots ran by hand on 2026-10-03 (both rigs idle before and after; every launch
command is in `records/evidence/2026-10-03-jev-mcorch/`), the campaign scripts are
under `tools/runs/campaigns/jev-mcorch/` and run only through the door
(`python -m mcgyvr.serving.run`). Every figure here is about a config tag, never
about a rig (`okf/must-read/always.md`).

**Prediction.** A Jev under ~4B dense cannot judge whether a change passes its
tests from the first token: the 1.5B–8B candidates say Yes on 74–100% of rows
and rank pass/fail at AUROC 0.44–0.67 (pilot P1, §2.2). The reviewer's
`verdict` question — which sees `original` and `change` whole — carries signal
from 8B up (AUROC 0.73–0.75 at 14B dense and 30B-A3B). So the owner's "bump the
Jev, lower the orchestrator" trade is real in one direction: the Jev that helps
is a mid-size model, and the one checkpoint that can serve as both Jev and
orchestrator today is Qwen3-Coder-30B-A3B. The run decides whether a cheaper Jev
(Qwen3.5-4B/9B, gemma-3-4b, Qwen3-4B-2507) reaches the 30B's `verdict` AUROC,
and whether the 30B-A3B class can drive the harness's tool loop at all.

## 0. What changed in the brief (owner, 2026-10-03, relayed)

mcorch is a **model**: it serves the Anthropic Messages API (`/v1/messages`,
streamed) to Claude CLI (`ANTHROPIC_BASE_URL`) and pi (`anthropic-messages`
provider). The harness's own tools (read, edit, bash, grep) are offered to the
orchestrator rung and the harness executes the rung's tool calls in the user's
cwd; contracts run as the rung emitting `bash mcgyvr run … --repo .`, the skill
flow. The harness system prompt (~15–20k tokens from Claude CLI) is replaced by
a compact mcorch prompt. Jev answers **J1** intent (chat/work/status/abort),
**J2** contract `ready_to_run`, **J3** next (done/replan/ask_user/abort).
Decision 0013 (api-tier-only decomposition) is rescinded. §4 steps 6–7 and §5
carry this; D/P/J (step 4) stays as the contract-authoring comparison because
the rung still has to author a contract inside the loop.

## 1. What exists (read from code and records, 2026-10-03)

### 1.1 Jev, in the product (`product/` at 417a2a9b)

| fact | where |
|---|---|
| One request per question, `max_tokens: 1`, `temperature: 0`, `logprobs`, `top_logprobs = min(20, labels)`; answer = normalised probability over the label tokens in the first token's `top_logprobs`; a reply with no label raises `DecisionError` | `product/src/mcgyvr/decision.py:58-59`, `:200-215`, `:300-320` |
| The body carries **no `chat_template_kwargs`** and the prompt is one user message | `decision.py:304-312` |
| Gate rung: `satisfies_task`, `in_scope` (Noul), `regression_risk` (Score low/medium/high) over `{task, path, added_lines}` per changed file; report-only | `product/src/mcgyvr/gate/jev.py:63-71`, `:184-201` |
| Reviewer typed verdict: one Noul over `{task_type, task, target, interface, deterministic_gate, original, change}`, prose fallback | `product/src/mcgyvr/verify.py:145-148`, `:347-370` |
| `ClassifierProposer` (J): `kind`, `target`, `symbol` Choices, refuses under confidence 0.5; **not wired** — `cli.py:_delegate` calls `proposer_for` only | `product/src/mcgyvr/delegate.py:359-360`, `:372-460`; `product/src/mcgyvr/cli.py:889-915` |
| `triage.py` has no caller in `src/` | `product/tests/test_triage.py:26` only |
| Roles: `orchestrator.unit` / `verifier.unit` in policy.yaml; `fast_rung` = first keyless ladder rung | `product/src/mcgyvr/config.py:2033-2037`; `product/src/mcgyvr/fleet_manager.py:141-151` |
| No fleet.yaml in either repo binds `orchestrator` or `verifier` | `fleet-setup/fleet.yaml`, `fleet-setup/policy.yaml:6-7` |
| **No Jev accuracy or calibration figure exists in either repo** (all Jev code is from 2026-10-01: 5117ce2f, b8c148aa, e164cfdf, 97c211c3) | grep of both trees, `records/evidence/calibration-2026-08-19` is serving-constant calibration |

### 1.2 Labelled data

| set | rows | label | grounds | where |
|---|---|---|---|---|
| bench rows: contract + stored whole-file candidate + shipped gate verdict | 8,969 under `bench-py` (35,014 with ts and other dirs); pass pool 1,458, `rejected_by=acceptance` pool 987 after the slice filter | `passed` (tools/bench/score.py) | `satisfies_task`, `verdict`; by model pairing `wake_smarter` / `floor` | `records/measurements/*/bench-py/results.jsonl`, `…/candidates/<task>/<arm>-<draw>.txt`, `tools/bench/tasks/py/<id>/contract.yaml` |
| the campaign slices (keys + labels only, content re-derived at run time) | 80 (pilot) / 400 (run), balanced, 77 / 212 tasks | same | same | `tools/runs/campaigns/jev-mcorch/slice-80.jsonl`, `slice-400.jsonl`, built by `build_slice.py` (seed 20261003) |
| `in_scope`, `regression_risk`, `symbol`, J1/J2/J3 | **none** | — | — | to be labelled (§6 Q3) |
| reach corpus: 77 commits → source files | 77 | commit subject → files | `target` Choice (no negatives) | `records/corpora/reach-2026-08-02/corpus.json:17` |

### 1.3 Engines (pinned images, read on the rigs 2026-10-03)

| fact | source |
|---|---|
| llama.cpp `llamacpp:b10644-L3-rpc` = `sha256:c49d9cd3e2d6…` on both rigs; entrypoint `/app/llama-server`; `--jinja` default on; `-rea/--reasoning on|off|auto`; `--reasoning-budget N`; `--cache-reuse N` (default 0); `--slot-prompt-similarity` 0.10; `--cache-ram` 8192 MiB; `-np -1 = auto` | `records/evidence/2026-10-03-jev-mcorch/llama-server-b10644-flags.txt` |
| llama.cpp `top_logprobs` are a **pre-sampling softmax over the full vocabulary** (temperature not applied), no cap at 20; `post_sampling_probs` is a separate option | b10644 `tools/server/server-common.cpp#L1496-L1546`, `server-schema.cpp#L179-L191` (online research, URLs in §7) |
| vLLM `vllm/vllm-openai:v0.26.0` = `ffb2d59b1c05` on both rigs; `--logprobs-mode {raw_logprobs,…}` (default raw), `--max-logprobs` default 20, `--enable-prefix-caching` default on (V1), `--tool-call-parser {…,qwen3_coder,qwen3_xml,hermes,glm45,glm47,gemma4,…}`, `--default-chat-template-kwargs` | `records/evidence/2026-10-03-jev-mcorch/vllm-v0.26.0-flags.txt` |
| vLLM `logprob_token_ids` (per-request exact label ids, bypasses top-20) exists at v0.30.0; **not checked on v0.26.0** | `vllm/entrypoints/openai/chat_completion/protocol.py#L287-L299` @v0.30.0 |
| Turing (sm75) still supported by vLLM, fp16 only, no FlashAttention; `llamacpp:b10644-L3*` is the Turing-safe build (compute_61 PTX, MMA off) | `records/evidence/2026-09-27-l3-rpc-build/PROVENANCE.txt:10`; `okf/must-read/touching-engine.md` |
| On the 1660S llama.cpp beats vLLM at every width; on a 3060 vLLM is ~4× llama.cpp aggregate at n=128 and ~equal at n=1 (1.5B: 184 vs 176 tok/s) | `records/evidence/2026-08-24-engine-sweep/srv2.log:24-39`, `srv1.log:20-77` |

### 1.4 Rigs, read live 2026-10-03 16:56 UTC (re-read before every launch)

| host | cards | RAM avail | disk | models |
|---|---|---|---|---|
| srv1 | 2× RTX 3060 12288 MiB, cc 8.6, driver 580.178.04, 11909 MiB free each | 44 GiB | `/` NVMe 85 GB free (holds `~/models → ~/models.bak`, what the drivers mount as `/models`); `/data` HDD (rotational=1) 2.3 TB free (`/data/models`, 344 GB) | headers of all 35 GGUFs: `records/evidence/2026-10-03-jev-mcorch/headers-srv1.jsonl` |
| srv2 | 1× GTX 1660 SUPER 6144 MiB, cc 7.5, 5729 MiB free | 44 GiB | `/` 269 GB free (`~/models` 247 GB, HF cache 193 GB) | `headers-srv2.jsonl` |

A load from `/data` (HDD) took 111 s for the 12 GiB 30B-A3B against 36 s for the
8.4 GiB 14B from NVMe (`p1-sweep-srv1.log`); the fill step's Coder-Next
(33.8 GiB) lives on `/data` only.

### 1.5 Prior measurements the plan stands on

| figure | config tag / cite |
|---|---|
| Coder-30B-A3B both cards: dec 101.7 tok/s, pp 1997 tok/s, 30k-token TTFT 15.6 s local vs 57.3 s over RPC | `records/evidence/2026-10-01-rpc-split/pair-a3b-local.tsv:10-11`, `ctx.tsv:10,16` |
| Coder-Next UD-Q3_K_XL tensor cm24: dec 29.2, pp 64.8, TTFT 23.6 s at 1.5k tokens, 455.8 s at 30.5k | `records/evidence/2026-09-29-srv1-multi-gpu/biggest-coder.tsv:13-15`; `2026-09-30-…/biggest-coder-fill.tsv:18-19` |
| Qwen3-Next-80B tensor cm24: dec 36.7, pp 128.4 | `2026-09-30-srv1-multi-gpu/biggest-coder-fill.tsv:21-22` |
| `--n-cpu-moe` floors: Coder-Next 24 (two cards) / 40 (one); 30B-A3B 0 (two) / 24 (one) | `biggest-coder.tsv:11-12`, `biggest-coder-fill.tsv:9-10`, `2026-09-27-srv1-multi-gpu/offload.tsv:9-10` |
| fp8 KV: 7B 68 → 6/257 passes; llama.cpp q8_0 KV 67 vs f16 69 | `records/measurements/kv-dtype-2026-09-11/README.md:47`, `:78-82` |
| RPC split costs −13…−29% decode and 3–4× TTFT; pooled slots S4 +67% over S1 | `records/evidence/2026-10-03-pooled-slots/README.md:53-70`, `:112-117` |

## 2. Pilots (2026-10-03, by hand, both rigs left idle)

All files under `records/evidence/2026-10-03-jev-mcorch/`; harness scripts under
`harness/`; the exact `docker run` of every launch is the `launch:` line in
`p1-sweep-srv1.log` / `p1-sweep-srv2.log` / `harness/p3_run.sh`.

### 2.1 P0 — what the engine hands `decision.classify`

Config `lcp-qwen3-4b-q4km-*`: `llamacpp:b10644-L3-rpc`, `/models/dense/Qwen3-4B-Q4_K_M.gguf`,
srv1 card 0, `-c 16384 -np 1 --jinja -lv 4 --no-warmup`, 4899 MiB on the card.

| arm | first token (p) | readable by the primitive | warm wall, 300-token state | file |
|---|---|---|---|---|
| template as shipped (what the product sends) | `<think>` (1.000), next `</think>` (e⁻¹³) | **0 of 4 questions** — `DecisionError` on every one | 0.17 s | `p0-qwen3-4b-default.jsonl` |
| + `chat_template_kwargs {"enable_thinking": false}` (product does not send it) | `Yes` (1.000) / `1` (0.997) / `C` (1.000) | 4 of 4 | 0.19 s (301 of 305 tokens cached) | `p0-qwen3-4b-nothink.jsonl` |
| server `--reasoning off` | same as above | 4 of 4 | 0.19 s | `p0-qwen3-4b-reasoning-off.jsonl` |

Reading: on any thinking-by-default template the shipped request body reads
`<think>` and the rung reports every file as "not judged". The fix is a launch
flag, not code (`--reasoning off`); the unit's `--reasoning` is therefore part of
the Jev config tag. Probabilities are a full-vocab softmax at temperature 0, so
confidence 1.000 on a 4B is the model's over-confidence, not clipping.

### 2.2 P1 — the Jev ladder over the 80-row slice (`p1-slice.jsonl`)

Label = the shipped gate's `passed`; 40 pass / 40 `rejected_by=acceptance`,
77 tasks, source models 1.5B–7B. Four questions per row through
`decision.classify` (gate/jev.py's three over `{task, path, added_lines}`,
verify.py's `verdict` over `{…, original, change}`). AUROC SE at n=80 ≈ 0.06.

| config tag | card MiB | load s | row (4 q) med s | `satisfies_task` acc / AUROC / Brier / yes-rate | `verdict` acc / AUROC / Brier / yes-rate | `regression_risk` mean level pass / fail |
|---|---|---|---|---|---|---|
| `lcp-qwen25c-1.5b-q4km` | 1589 | 26 | 0.81 | 0.50 / 0.60 / 0.31 / 1.00 | 0.50 / 0.51 / 0.26 / 1.00 | 1.28 / 1.28 |
| `lcp-qwen25c-3b-q4km` | 2633 | 27 | 0.95 | 0.50 / 0.58 / 0.38 / 1.00 | 0.50 / 0.48 / 0.34 / 1.00 | 1.00 / 1.03 |
| `lcp-qwen3-4b-q4km-rea-off` | 4899 | 20 | 1.02 | 0.44 / 0.44 / 0.53 / 0.89 | 0.51 / 0.55 / 0.47 / 0.91 | 1.11 / 1.13 |
| `lcp-qwen35-4b-supercoder-q40-rea-off` | 3189 | 51 | 1.60 | 0.58 / **0.67** / 0.24 / 0.68 | 0.65 / 0.57 / 0.27 / 0.70 | 0.71 / 0.84 |
| `lcp-qwen25c-7b-iq4xs` | 4915 | 29 | 1.03 | 0.46 / 0.62 / 0.40 / 0.96 | 0.53 / 0.56 / 0.42 / 0.98 | 1.11 / 1.20 |
| `lcp-qwen3-8b-q4km-rea-off` | 7001 | 29 | 1.18 | 0.51 / 0.58 / 0.46 / 0.74 | 0.50 / **0.75** / 0.48 / 1.00 | 0.65 / 0.96 |
| `lcp-qwen25c-14b-q4km` | 10823 | 36 | 1.83 | 0.59 / 0.65 / 0.26 / 0.64 | **0.71 / 0.73 / 0.21** / 0.71 | 0.57 / 0.87 |
| `lcp-qwen3coder-30b-a3b-iq3xxs-layer2` (both cards) | 7033 + 7171 | 111 | 1.24 | 0.59 / 0.63 / 0.41 / 0.51 | **0.71 / 0.75** / 0.28 / 0.61 | 0.99 / **1.52** |
| `lcp-ling3-tiny-q4km` (bailingmoe3 MoE) | 4885 | 42 | – | `DecisionError` 80/80: no label in top_logprobs | – | – |

Files: `p1-lcp-<tag>.jsonl` (one line per row + a `summary` line), `p1-sweep-srv1.log`.

Reading, per the rules (data points, not a ranking):
- Below 8B every candidate answers Yes on ≥ 74% of rows; the ranking signal on
  `satisfies_task` is ≤ 0.67 AUROC and the best of it (Qwen3.5-4B-super-coder)
  is the one coder-tuned 4B. `added_lines` alone is a thin state.
- `verdict` (the whole `original` + `change`) is the question that works:
  0.73–0.75 AUROC and 0.71 accuracy at 14B dense and 30B-A3B; 0.75 AUROC but
  yes-rate 1.00 at 8B (ranks, does not calibrate at the 0.5 threshold).
- `regression_risk` separates pass from fail only on the 30B-A3B (0.99 vs 1.52).
- Latency is not the constraint: 0.8–1.8 s for four questions over ~1k-token
  states, prefix-cached, one slot.
- Ling-3.0-tiny's first token is never a label (reads `DecisionError`); the
  cause (template or tokenizer surface form) is step 0's job before it is
  ruled out.

### 2.3 P2 — orchestrator modes D / P / J, and P3 — the rung as the harness's model

Config `lcp-c30-a3b-iq3xxs-layer2-32k`: `/data/moe/Qwen3-Coder-30B-A3B-Instruct-UD-IQ3_XXS.gguf`,
both cards `-sm layer`, `-c 32768 -np 1 --jinja`, 5.9 + 6.1 GiB weights, 1.6 + 1.5 GiB KV.
Repos: five bench tasks as git repos (`harness/p2cfg`, `make_repos.py`), the
reference solution withheld.

**P3 — the tool loop** (`harness/tool_loop.py`: compact mcorch prompt ~700
tokens, four tools over `/v1/chat/completions` with `tools`, the harness
executing the rung's calls in a clone; `p3-toolloop.jsonl`, `p3-contracts/`,
`p3-run-results/`):

| repo | turns | wall s | tool calls parsed / unparsed / bad args | contract written → `mcgyvr contract` → `mcgyvr run` | run outcome | then | accept.py passes | prefix cached |
|---|---|---|---|---|---|---|---|---|
| b073-bump-release | 16 | 38 | 15 / 0 / 0 | yes → ok → yes | `error` (preflight) | edited `solution.py` itself, wrote its own test | yes | 43.7k of 45.7k tokens (95%) |
| b002-option-pairs | 20 (cap) | 96 | 19 / 0 / 0 | yes → ok → yes | `error` (preflight) | edited target itself | yes | — |
| b004-install-order (bug_fix) | 11 | 18 | 10 / 0 / 0 | **no contract** | — | fixed target directly | yes | — |
| b252-swipe-dedupe | 15 | 28 | 14 / 0 / 0 | yes → ok → yes | `error` (preflight) | edited target itself | yes | — |

Per-turn wall 0.5–7 s at 1.1k–4.8k prompt tokens (TTFT-bound; decode 88 tok/s,
prefill 1.3k tok/s from the server log). Every tool call the rung emitted was
parsed by llama.cpp's template parser (Qwen3-Coder XML); arguments were valid
JSON every time.

The `mcgyvr run` outcomes are the product's preflight, not the model:
`acceptance-mutates-tree` (`python accept.py` writes `__pycache__`) and, with
`-B`, `acceptance-baseline-failing` (the stub fails its own tests, and
`acceptance` must be green on the unchanged tree — the task's tests belong in
`demonstration`). The rung read those result files and then broke the prompt's
one rule ("never edit the target yourself"): 4 of 4 loops finish by direct
edit, which is what the harness's `accept.py` then rewards. **Two things the
run must change:** the corpus (`make_repos.py` now emits a green `acceptance`
and the tests as `demonstration`), and the harness jail — in the first b002
attempt the rung ran `cd /tmp && mkdir test_dir && cp -r ./* test_dir/`
(1.9 GB copied before it was killed; removed). `tool_loop.py` now refuses any
path outside the clone, the run envelope and mcgyvr's state. mcorch's real
harness must do the same, or run under the harness's own permission prompts.

**P2 — D / P / J** on the same rung (`p2-modes.jsonl`, `p2-modes-pj.jsonl`,
`p2-contracts/`):

| mode | valid contracts / 5 | target right | type right | wall / repo | why not |
|---|---|---|---|---|---|
| D (SKILL.md in context, ~5.3k prompt tokens) | 1 | 1 | 1 | 1.5–5.9 s | `target_content` with `"""` breaks the YAML; `stop_conditions` empty (×2); bug_fix tests in `acceptance` not `demonstration` |
| P (`mcgyvr delegate`, proposer_for) | **5** | 4 (b073 → `accept.py`) | 4 (b004 bug_fix → function_implementation) | 4.3–4.8 s | — |
| J (`classifier_proposer_for` via `decompose`) | **0** | — | — | 1.1 s | every contract refused: `acceptance: is empty` — the typed proposer fills no acceptance/demonstration (decompose's `_acceptance_for` finds no adapter command in these repos; P's prose proposal carries one) |

P needed `orchestrator.model` spelled beside `orchestrator.unit`: `pool.py:445-456`
skips the role silently without it, while SETUP.md says absent means the unit's
own (only `verifier` gets that fallback). Filed in §7.

### 2.4 P4 — the Jev on srv2's card (GTX 1660 SUPER)

Same image (`llamacpp:b10644-L3-rpc` = the Turing-safe L3 build), same slice,
same driver, srv2 card 0 (`-c 16384 -np 1 --reasoning off`). Files
`p1-sweep-srv2.log`, `p1-lcp-*-srv2.jsonl`.

| config tag | card MiB | load s | row med / p90 s (3060 figure) | `satisfies_task` AUROC (3060) | `verdict` AUROC (3060) |
|---|---|---|---|---|---|
| `lcp-qwen3-4b-q4km-rea-off-srv2` | 4672 | 21 | 1.74 / 2.60 (1.02 / 1.20) | 0.443 (0.444) | 0.557 (0.552) |
| `lcp-qwen35-4b-supercoder-q40-rea-off-srv2` | 3158 | 23 | 2.69 / 3.69 (1.60 / 1.97) | 0.664 (0.672) | 0.588 (0.574) |

Reading: the answers are the model's, not the card's (AUROC agrees within
0.01–0.02 across cards at temperature 0), and the 1660S costs 1.7× the wall of a
3060 at width 1 — 1.7–2.7 s for four questions, still far under a worker
dispatch. A 4B Jev on srv2's card leaves both srv1 cards to the rung; the
6 GB card holds a 4B at 16k with ~1.5 GB spare, so a 7–9B Jev there needs a
smaller window or a deeper quant (step 2 names the edge).

## 3. What the pilots decide now, and what they leave to the run

| question | evidence-based answer today | conviction | the run's job |
|---|---|---|---|
| Tiny Jev viable? | **Not for pass/fail judgment of code** from `added_lines`: 1.5B–4B are at chance (§2.2). Viable for the single-token *mechanics* (every label read, 0.2 s warm) and so a candidate for the cheap routing questions (J1 intent, wake-smarter, `kind`) once those have labels | 90% on the code-judgment finding (8 configs, one slice; n=80); 60% on the routing use (no labels yet) | step 1 at n=400 on 11 candidates incl. the current small instruct models (Qwen3-4B-2507, Qwen3.5-2B/4B/9B, gemma-3-4b) |
| Bigger Jev, smaller orchestrator? | The Jev that carries signal is 14B-dense or 30B-A3B class — *the orchestrator's own size*. The one-checkpoint design (30B-A3B serves Jev and rung) is the cheapest honest configuration today; a separate 4B Jev buys nothing on the verifier questions | 85% | steps 1/4/6: does Qwen3.5-9B (5.7 GB) reach `verdict` AUROC ≥ 0.73; can a 30B-A3B-class rung run the tool loop (step 6) so that one unit does both |
| Best Jev engine | llama.cpp: logprobs are a raw softmax (no temperature, no cap), `--reasoning off` is a server flag, prefix cache hit 269–301 of ~300 tokens with no tuning, Turing build exists; vLLM adds nothing the primitive uses at width 1 and costs a second CUDA context beside the rung | 80% | step 3 (vLLM AWQ twins on the same slice: fidelity, warm wall, footprint) |
| Can a 30B-A3B-class rung drive the harness's tool loop? | Mechanically yes: 58 of 58 tool calls parsed by llama.cpp's Qwen3-Coder template, valid JSON arguments, 95% prefix reuse, 0.5–7 s per turn at ≤ 5k tokens. Behaviourally no, not yet: it abandons the contract flow after one `error` result and edits the target itself (4/4), and it left the repo once (`cd /tmp && cp -r`). The prompt, the jail and the result-file wording are the levers before model size is | 80% on the mechanics (one model, 4 repos); 70% on the behaviour (the preflight errors it read were the corpus's fault) | step 6 on 5 candidates with the fixed corpus and jailed harness: loops that reach `accepted` through `mcgyvr run` without a direct edit |
| Jev placement | Co-resident on card 0 beside a layer-split rung, or served by the rung itself; srv2's card is the alternative if the fill (step 5) shows the Jev's 3–7 GiB costs the rung a `--n-cpu-moe` step | 70% | steps 2, 5 |

## 4. Measurement plan

Rules: `okf/must-read/touching-rigs.md` (read the card live, `free` not
`total−reserve`, retry a refusal three times, kill what you started),
`reading-results.md` (first request is cold; compare verdicts not bytes; n=1
rows are TTFT-bound), `touching-engine.md` (fits → vLLM, else llama.cpp with
`--n-cpu-moe`; Turing on the L3 image), `config/llama.cpp.md` (`-c` divides
across slots only with `--parallel`; `-lv 4` on every launch whose log is the
readback). Every row names its config tag and `img=`.

### 4.1 Instrument

`tools/runs/campaigns/jev-mcorch/` — `campaign.json`, `_jev.sh` (door shims,
`lcp_up` / `vllm_up` / `unit_down`, GPU and HOST rows, srv1 or srv2), drivers
`jev_probe.py` (step 0), `jev_slice.py` (steps 1–3, the product's own
`decision.classify` with a real `Endpoint`), `orch_modes.py` (step 4, D/P/J; J
wired here), `tool_loop.py` (steps 6–7, the harness player and the context
ladder), `make_repos.py`, `build_slice.py`, `slice-80.jsonl`, `slice-400.jsonl`.
Lint and types pass (`ruff`, `mypy` under the lab's `make check` settings); the
steps are launched only through `python -m mcgyvr.serving.run --host <rig>
--campaign jev-mcorch --step <file> --model <blob> --ctx-per-slot N`.
Evidence lands in `records/evidence/<date>-jev-mcorch/<artifact>.tsv`.

### 4.2 Matrix

**Use case 1 — Jev models for Jev functions** (steps 0–3)

| step | host / card | engine + flags | candidates (container path; HF repo, quant, size) | ctx / slots | data | metrics | stop rule |
|---|---|---|---|---|---|---|---|
| 0 fidelity | srv1 card 0 | llama.cpp `--jinja` default vs `--reasoning off`; vLLM `--logprobs-mode raw_logprobs --max-logprobs 20` (+`--default-chat-template-kwargs`) | Qwen3-4B Q4_K_M (on disk); `thewimo/Qwen3-4B-AWQ` (cached); Ling-3.0-tiny Q4_K_M (on disk, the P1 refusal) | 16k / 1 | fixed state, 4 questions, `--pad 300` arm | first token + p, readable, warm wall, cached tokens | a candidate whose shipped-template first token is not a label is run only with the flag that fixes it, and the flag joins its tag |
| 1 ladder | srv1 card 0 | llama.cpp as step 0 | on disk: Qwen2.5-Coder 1.5B/3B/7B(IQ4_XS)/14B Q4_K_M, Qwen3-4B, Qwen3-8B, Qwen3.5-4B-super-coder Q4_0; **download** (unsloth GGUF, decimal GB): Qwen3-4B-Instruct-2507 Q4_K_M 2.50, Qwen3.5-2B Q8_0 2.01, Qwen3.5-4B Q4_K_M 2.74, Qwen3.5-9B Q4_K_M 5.68, gemma-3-4b-it Q4_K_M 2.49 | 16k / 1 | `slice-400.jsonl` (200/200, 212 tasks) | per candidate: acc, AUROC, Brier, ECE10, yes-rate for `satisfies_task` and `verdict`; `regression_risk` level by label; row wall med/p90; card MiB; load s | a candidate with > 5% `DecisionError` rows is filed REFUSED-on-protocol, not scored; the ladder stops adding size once two consecutive sizes are within the n=400 tie bar (AUROC ±0.03) |
| 2 srv2 | srv2 card 0 (1660S) | llama.cpp L3 image | the step-1 candidates ≤ 7B | 16k / 1 | same slice | same + wall (the placement figure) | quality figures must agree with step 1's within ±0.03 AUROC or the card changed the answer → investigate the build |
| 3 vLLM | srv1 card 0 | vLLM v0.26.0 fp16, util 0.45, `--max-num-seqs 4` | cached AWQ: Qwen2.5-Coder-1.5B/3B/7B-AWQ, `thewimo/Qwen3-4B-AWQ` | 16k / 4 | same slice | same; plus footprint at util 0.45 and the engine's KV readback | if AUROC differs from the GGUF twin by > 0.05, the quant/engine pair is a semantic key and both stay in the matrix |

**Use case 2 — the rung as the conversational agent** (steps 4, 6, 7)

| step | host | engine + flags | candidates (both cards `-sm layer`) | ctx / slots | data | metrics | stop rule |
|---|---|---|---|---|---|---|---|
| 4 orch-modes | srv1 | llama.cpp `--jinja`; `--reasoning off` on thinking templates; Jev unit on card 0 (`JEV_MODEL`) bound as verifier and J's classifier | on disk: Coder-30B-A3B UD-IQ3_XXS (/data), Qwen3.6-35B-A3B UD-IQ3_XXS, gpt-oss-20b MXFP4, Coder-Next UD-Q3_K_XL (/data, cm24); **download**: `unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF` UD-Q4_K_XL 17.67 GB, `unsloth/GLM-4.7-Flash-GGUF` UD-Q4_K_XL 17.52 GB | 32k / 1 | 5 bench repos (`make_repos.py`), prompt = contract task + test command | per (repo, mode): emitted, valid, target/type match, wall, D's prompt/completion tokens, J refusal; per contract: `mcgyvr run` outcome, rungs | a mode with 0/5 valid on two candidates is dropped from later candidates |
| 6 tool-loop | srv1 | same; tool calls parsed by the engine (`--jinja` + GGUF template; flags on the LAUNCH row) | same candidates | 64k / 1 | same repos; compact mcorch prompt + 4 tools | per turn: wall (TTFT-bound), prompt/completion/cached tokens, parsed calls, unparsed call-text; per repo: turns, contract written, `mcgyvr run` invoked, result outcome, accept.py passes, finished in plain text, max prompt tokens | a candidate that emits unparsed tool text on > 20% of turns is filed as "no tool protocol" and its vLLM parser twin is queued |
| 7 ctx-cost | srv1 | same | same | 4k…64k | synthetic mcorch transcript (tool results), cold then +1 turn | cold wall (prompt processing tok/s), warm wall, cached tokens | TTFT > 30 s at 32k cold on a candidate removes it from the "conversational" column, not from the ladder |

**Use case 3 — fill the hardware** (step 5)

| cells (`mgpu_sweep.py`, `@knob` + `@prefill=2800`) | placement | what it decides |
|---|---|---|
| Jev (Qwen3-4B or step-1 pick, card 0) + Coder-Next UD-Q3_K_XL `--n-cpu-moe 28/26/24/22`, layer, 32k | both cards + host RAM (33.8 GiB blob must fit 44 GiB avail: it does, mapped) | the floor beside a Jev, and its decode/TTFT cost vs step 22/23 (cm24: 29.2 tok/s, 23.6 s TTFT) |
| Jev + Coder-30B-A3B UD-Q4_K_XL cm0, 32k and 131k | both cards | the "one 30B does both" configuration's KV ceiling beside a Jev |
| the same without the Jev | — | what the Jev costs the rung |
| cross-rig `--rpc` | **not run**: priced already (−13…−29% decode, 3–4× TTFT: §1.5); a Jev on srv2's card takes RPC0 anyway | — |

### 4.3 Run order and wall-clock (estimates from the pilots' per-row and load times)

| order | step | host | est. |
|---|---|---|---|
| 1 | downloads to srv1 `~/models` (NVMe): 5 Jev GGUFs 15.4 GB + 2 orchestrator GGUFs 35.2 GB ≈ 50.6 GB; copy Coder-30B UD-Q4_K_XL to srv2 for step 2? no — step 2 is ≤ 7B | — | bandwidth-bound |
| 2 | 0 fidelity | srv1 | 15 min |
| 3 | 1 ladder (11 × ~400 rows × ~1.5 s + loads) | srv1 | 2.2 h |
| 4 | 2 srv2 (7 candidates) | srv2 | 1.5 h (runs in parallel with 3) |
| 5 | 3 vLLM (4 × load 2–3 min + 400 rows) | srv1 | 50 min |
| 6 | 4 orch-modes (6 candidates × 5 repos × 3 modes + runs) | srv1 | 2.5 h |
| 7 | 6 tool-loop + 7 ctx (5 candidates) | srv1 | 2.5 h |
| 8 | 5 fill (9 cells, Coder-Next loads from HDD ~4 min each) | srv1 | 1.5 h |
| | total rig time | | ≈ 9.5 h srv1, 1.5 h srv2, over 2–3 sessions |

### 4.4 Disk plan

Downloads (srv1 `~/models/dense|moe`, 85 GB free → ~34 GB after): the seven
GGUFs in §4.2. srv2 (`~/models`, 269 GB free): the five Jev GGUFs (15.4 GB) for
step 2. **No deletion in this stage.** Candidates for a later cleanup, each to
be grepped against `fleet-setup/`, `records/fleet/` and `tools/runs/campaigns/`
before any `rm`, and hashed if a twin exists (`touching-models.md`): srv1
`~/models.bak/dense/Qwen2.5-Coder-32B-Instruct-Q4_K_M.gguf` (19.9 GB; the Q5_K_M
is the pooled head), `nvidia_OpenCodeReasoning-Nemotron-7B-Q4_K_{M,S}.gguf`
(9.1 GB), `/data/models/moe/{qwen3-coder-30b.gguf, gpt-oss-20b.gguf}` (the
`gptoss`-arch and ollama-era blobs, 30 GB). Every deletion, if approved, is
logged in the evidence dir with path and size.

### 4.5 What each result decides for the code

| result | decision |
|---|---|
| step 0: shipped template unreadable on candidate X | the Jev unit's compose carries `--reasoning off` (or vLLM `--default-chat-template-kwargs`); `decision.classify` stays as is — **or** the code agent adds `chat_template_kwargs` to the body (owner's call, §6 Q1) |
| step 1: best `verdict` AUROC per size class | default Jev model for the verifier role; `_REGRESSION_LEVEL` and `MIN_CONFIDENCE=0.5` re-set from the calibration curves (`data/numbers.json:212-215` names 0.5 a choice with no measurement) |
| step 1: `satisfies_task` stays ≤ 0.67 on every candidate | gate/jev.py's state is widened to carry `original`/`change` like verify.py's, or the rung keeps reporting only |
| step 4: D vs P vs J valid-contract and run-acceptance rates | which proposer `mcorch` uses to author a contract inside the loop; J is wired to the CLI only if its refusal rate < 30% and its accepted-run rate ≥ P's |
| step 6: tool-loop completion per candidate | the orchestrator rung for mcorch (the smallest candidate that reaches `outcome: accepted` through `mcgyvr run` on ≥ 4/5 repos with no direct edit of the target and ≤ 1 unparsed turn); a candidate that completes only by direct edit is filed as such, not as a pass |
| step 6: direct-edit rate | whether mcorch's prompt alone holds the rule, or the adapter must refuse `write_file`/`edit` on the contract's target while a contract is open (a code decision for the mcorch PR) |
| step 7: cold TTFT per context | the compact prompt budget and whether `--cache-reuse` / slot pinning is worth a code change |
| step 5: floor with Jev resident | mcorch placement: Jev co-resident on card 0, served by the rung itself, or on srv2 |

## 5. Phases

| phase | what | gate |
|---|---|---|
| P0 (done) | pilots above | — |
| P1 | steps 0–3 (Jev) | owner approves this plan |
| P2 | steps 4, 6, 7 (rung as agent) | P1 names a Jev to co-host |
| P3 | step 5 (fill) | P2 names the orchestrator candidates that complete the loop |
| P4 (later) | end-to-end through real pi / Claude CLI against `/v1/messages`: the same 5 repos plus two real repositories, scoring replan quality after findings and multi-turn conversation; J1/J2/J3 Jev questions over labelled transcripts | the code agent's mcorch PR exists; labels for J1–J3 exist (§6 Q3) |

## 6. Open questions for the owner (below the 90% floor)

1. **Fix for the thinking template**: launch flag per Jev unit (`--reasoning off`, no code) or `chat_template_kwargs: {enable_thinking: false}` in `decision.classify`'s body (code, portable across engines)? The pilot shows both work on llama.cpp; vLLM needs `--default-chat-template-kwargs` or the body field.
2. **The Jev state for the gate rung**: `added_lines` alone is at chance on every candidate; may the rung's state carry the whole `original`/`change` (what verify.py sends), at the prompt-size cost (~1k → ~2–4k tokens)?
3. **Labels for J1/J2/J3, `in_scope`, `regression_risk`**: none exist. Proposal: 60 hand-labelled items each, drawn from the step-6 transcripts (J1 intent and J3 next are readable from a transcript; J2 from the contract + `mcgyvr contract` output). Who labels — owner, or the API-tier agent with owner spot-checks?
4. **API-tier reference arm (Ref)** for steps 4/6: run the same 5 repos through the owner's API agent for a ceiling? Costs API money; not run without the OK.
5. **Downloads**: ~50 GB to srv1 NVMe (§4.4) — approve the list, or trim.
6. **The harness jail**: pilot P3's rung ran `cd /tmp && cp -r ./* test_dir/`. For the run the harness refuses paths outside the clone (done). For mcorch itself: rely on Claude CLI's / pi's own permission prompts, or have the adapter deny tool calls outside cwd? The campaign can measure either; it needs the ruling to know what to score as a refusal.
7. **Corpus shape for steps 4/6**: `mcgyvr run` needs `acceptance` green on the unchanged tree and the task's tests as `demonstration`; bench tasks are stubs, so `make_repos.py` now emits `acceptance: python -B -c 'import <target>'` and `demonstration: python -B accept.py`. Acceptable as the E2E signal, or do you want repos with a real green suite (e.g. three small repositories of the owner's) instead?
8. **Slice size**: 400 rows (AUROC SE ≈ 0.025) per candidate at ~10 min each; or 200 to halve step 1.

## 7. Code blockers and notes for the code agent

- `ClassifierProposer` / `classifier_proposer_for` is not reachable from `mcgyvr delegate` (`cli.py:889-915` binds `proposer_for` only). Step 4 wires it in the harness; a `--proposer typed` flag would let the campaign use the CLI path.
- `decision.classify` sends no `chat_template_kwargs` (Q1).
- `pool.py:445-456`: the `orchestrator` role is skipped silently when `orchestrator.model` is absent, while `skills/mcgyvr/SETUP.md` says absent means the unit's own; only `verifier` has that fallback. `mcgyvr pool` prints no orchestrator line and `mcgyvr delegate` says "not configured".
- `ClassifierProposer` emits contracts with no `acceptance`/`demonstration` when the repo has no adapter-known test command (`orchestrator/decompose.py:_acceptance_for`), so every J contract on the pilot corpus failed validation while P's prose proposals carried `python accept.py`. J needs an acceptance source (the request text, or a Choice over commands found in the repo) before it can be compared.
- The gate's preflight wording (`acceptance-mutates-tree`, `acceptance-baseline-failing`) was read by the rung as "the tool is broken", after which it edited the target itself. The result file could name the fix (`-B`, move the command to `demonstration`) so a model-driven replan has something to act on.
- The gate rung's `build_state` carries added lines only (Q2).
- `mcgyvr run` requires `--orchestrator ID` outside a Claude Code / Pi session; the harness passes `RUN_ID`.
- Nothing in the product serves `/v1/messages` yet; steps 6–7 measure the rung over OpenAI chat/completions with `tools`, which is what the mcorch adapter will translate. Record the tool-call parser flags on every LAUNCH row so the adapter's engine choice is traceable.

## 8. Sources (online, 2026-10-03)

- llama.cpp b10644 server: `tools/server/server-common.cpp#L1375-L1384`, `#L1496-L1546` (pre-sampling softmax), `server-context.cpp#L1132-L1142` (`--cache-reuse`), `#L1467-L1517` (slot choice by LCP), `#L3233-L3265` (checkpoints on hybrid models), `tools/server/README.md#L593` (`post_sampling_probs`), `docs/autoparser.md#L244`, `#L478-L515` (tool formats tested: Qwen3-Coder XML, Hermes, GLM-4.6/4.7, MiniMax-M2, Nemotron-3-Nano, Granite 4, GPT-OSS, Llama 3.x) — https://github.com/ggml-org/llama.cpp/tree/b10644
- vLLM v0.30.0: `vllm/config/model.py#L254-L268` (`max_logprobs`), `#L101-L104` (`logprobs_mode`), `vllm/entrypoints/openai/chat_completion/protocol.py#L287-L299` (`logprob_token_ids`), `vllm/config/cache.py#L130` (prefix caching default), `docs/getting_started/installation/gpu.cuda.inc.md#L9` (cc 7.5 floor), `docs/features/quantization/gguf.md` — https://github.com/vllm-project/vllm/tree/v0.30.0
- Model cards and GGUF sizes: https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/tree/main , https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/tree/main , https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/tree/main , https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/tree/main , https://huggingface.co/unsloth/gemma-3-4b-it-GGUF/tree/main , https://huggingface.co/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF/tree/main , https://huggingface.co/unsloth/GLM-4.7-Flash-GGUF/tree/main , https://huggingface.co/unsloth/Qwen3-Coder-Next-GGUF/tree/main
- First-token vs written answer, surface-form competition: https://arxiv.org/abs/2402.14499 , https://arxiv.org/abs/2104.08315

# Use-case expansion — plan and decisions

mcgyvr grows from one use case (coding) to four, under two deployment models.
This file is the single source of truth for the decisions. The research
artifacts it builds on are `dedicated-models-shortlist.md`,
`media-capability-shape.md` and `measurement-plan-media.md`; the concept store
entries live in `okf/models/` (`c-*` diffusion, `d-*` speech, `e-*` context).

## Use cases — what mcgyvr is asked to do

| use case | gate | backend |
|---|---|---|
| coding | deterministic (lint · typecheck · tests) | llama.cpp / vLLM |
| chat | none — raw endpoint | llama.cpp / vLLM (OpenAI-compatible) |
| agent | grounded citations + safety + format | llama.cpp / vLLM + tool-calling |
| media-gen | media_valid · safety · ASR-WER | diffusers / ComfyUI + TTS engines |

## Deployment models — how mcgyvr is run

Two models, orthogonal to the use cases, chosen per use case at install.

- **hybrid** — an API-tier orchestrator (the model in the user's session) drives
  mcgyvr as a skill; scoped work is offloaded to the local cheap→dear ladder;
  the dearest rung is an API model, so a task always completes even when local
  fails. For media-gen that dearest rung is a hosted image/video/TTS API.
- **local-only** — mcgyvr is the backend and exposes endpoints; the user points
  any harness at it; there is no API tier.

Defaults: `chat` → local-only; `coding`, `agent`, `media-gen` → hybrid. Both
models are selectable for every use case at install.

## The orchestrator

Decomposes a request into scoped contracts, routes to ladder rungs, escalates
cheap→dear and judges against the gate.

- hybrid: the API model. No local cost; its concurrency is the API's.
- local-only: mcgyvr provisions a **local orchestrator unit** — a heavy,
  capable model with a generous context window, whose width (slot count) equals
  the number of users. It is resident first and consumes the VRAM/RAM the
  ladder rungs would otherwise use, so choosing local-only for a non-chat use
  case on single-user hardware is **flagged, not refused**.

## Models

Permissive-only by default; non-commercial opt-in. The ladders are in
`dedicated-models-shortlist.md`.

## Seams — coding-specific today

1. task catalog + evidence kinds → generalize
2. worker output protocol (one file) → PROSE / MEDIA_ARTIFACT
3. gate adapters (Python/JS) → media / safety / ASR / grounding
4. serving (llama.cpp/vLLM) → diffusers / ComfyUI / TTS
5. worker bundle (per language) → per use case
6. capability table (tok/s) → sec/image · sec/clip · RTF
7. okf concepts (text decode) → c/d/e entries

## Phases

- **P0** research → done (`3ef7c2fc`, `88ec9ccf`)
- **P1** generalize the core → increments 1–4 done (`97be405c` use_case axis,
  `42652ba4` evidence kinds, `3a229f73` prose schema, plus the gate output-check
  rung + contract params). Increment 5 (serving) done — 5a/5b/5c plus the
  seam 4 media engines: diffusers (image), TTS, and ComfyUI.
- **P2** media-gen vertical (image + tts first, video last)
- **P3** chat + agent verticals
- **P4** packaging (`mcgyvr init --use-case` + the deployment choice)

## Rulings

- chat is a raw un-gated endpoint; agent is the gated assistant — two use cases.
- consumer HW is the target: low VRAM/RAM, split-into-bites, offload to RAM.
- permissive-only default model ladder; XTTS v2 / F5-TTS / Flux-dev opt-in.
- hybrid default everywhere except chat; local-only default for chat.
- media-gen hybrid fallback is a hosted media API rung.
- local-only non-chat provisions a local orchestrator (slot = users), flagged on
  single-user HW.
- prose (chat/agent) and the orchestrator carry **no output cap** — a chatty
  model is a prompting/model issue, not a cap issue. Only `whole_file` keeps
  the cap, because a truncated file is a correctness hazard.
- P1 gate seam (increment 4): the four structural evidence kinds are wired into
  the gate as **output checks** (`mcgyvr.gate.output`), a new rung `Gate.run`
  runs only when the contract's type declares them. `media_valid` is a real
  magic-byte validator (image/audio/video headers, no heavy deps);
  `safety_pass` / `asr_wer` / `grounded` are P2 stubs that raise
  `ToolUnavailableError` — a check that never ran must not read clean. Their
  parameters are contract fields: `media_kind` (enum image/audio/video),
  `transcript`, `wer_threshold` (0–1), `sources` — each optional, required by
  cross-validation only when the type declares the matching evidence kind.
  `media_artifact` output schema stays a P2 (seam 2) concern.
- increment 5 (orchestrator unit, 5a/5b): the ruling is a pure, tested decision
  in `mcgyvr.orchestrator.local` — `local_orchestrator(use_case, local_only,
  users)` returns provision / width / flag. "Single-user hardware" is read as
  `users == 1`, the one count the decision can act on without a hardware model;
  the flag warns, never refuses. The count is a config fact: `users`, a whole
  number of at least 1, default 1. A written `width` on the orchestrator's unit
  wins over it — `users` is the fallback, not a second authority.
- increment 5c (resident-first serving, agreed): both role units enter the
  serving plan when local — the orchestrator and the verifier (only when
  `verifier.enabled`; the verifier is a Jev-like system model, served but never
  on the ladder, and it may also be an API unit). The orchestrator unit joins
  the ladder as its **dearest rung**: it is fitted against the full card first
  and sequenced first, ladder rungs are fitted against the card that remains,
  and its width is shared — `width = written width or users`, one slot reserved
  for the orchestration role, `width - 1` slots serving ladder concurrency.
  Done: 5c-1 (both role units enter `units_for` when local; the orchestrator
  joins the ladder as its dearest rung, its width the user count when
  unwritten), 5c-2 (resident-first: the orchestrator's process is fitted
  against the full card first, and the ladder and verifier on its host are
  fitted against the card minus its claim), and 5c-3 (the `width - 1` ladder
  reservation in `mcgyvr.capacity`, with the role's endpoint still carrying the
  served width). Review round found and fixed the co-residency regression
  (`resident_claim_gb`), the gate-stub docstring contradiction, the `Vram`
  invariant break, and four low findings (`records/review-p1-5a-5c.md`).
  Deferred and recorded: the `mcgyvr.orchestrator.local` *decision* (chat and
  hybrid provision nothing) is not yet wired into `units_for` — `units_for` is
  deliberately policy-free and serves any bound local role; the decision binds
  at P4 packaging, where the use-case and deployment choices are made.
  Open: seam 4's remaining media engines — TTS (RTF) and ComfyUI — and the P2
  media vertical. Seam 6 is open but not shipped: the capability table prices
  image and video in `seconds_per_image` / `seconds_per_clip` reading lists and
  carries the media row scalars (resolution, steps, vae_decode_gb, frames,
  temporal_compress, sample_rate_hz, rtf, cpu_only), yet no media row is
  shipped because a shipped estimate needs a measurement and none exists.
  Done — seam 4 first slice, `diffusers` (image): sized and rendered for real,
  from stated numbers only. A diffusers unit's card peak is the denoiser's
  resident working set plus the one-shot VAE decode spike
  (`vram_gb + vae_decode_gb`, c-01/c-03), judged with the scalar headroom;
  `disk_gb` is the disk claim and the stated `ram_gb` (once-per-run components
  offloaded to RAM) is the host claim — width 1, no window, no KV cache, no
  offload knob. The launch spec carries only stated values (the `hf_cache`
  weights directory, the port, the operator's `serve_args`); mcgyvr ships no
  diffusers server image or shell binary, so `units.<unit>.image` is required
  (refused by name when absent), the pasted-shell rendering is refused (the
  server is the image's entrypoint), and compose mounts the weights directory
  at its own absolute path. `KNOWN_ENGINES = (llama.cpp, vllm, diffusers)`;
  `fit`/`unit_for` refuse anything outside it by name, and `config.py`'s
  `engine` enum gained `diffusers`. Review-round rulings: `vae_decode_gb` must
  flow through BOTH `ModelSpec` bridges — the capability row
  (`mcgyvr.cli._model_spec`, decimal GB → GiB) and the `launch` block
  (`declared_models`, already GiB) — so a real emit does not drop the stated
  spike; and the `runtime_resident_gb` host-memory figure is a *text-engine*
  figure, so the three host-memory invariant tests are scoped to
  `RUNTIME_RESIDENT_KEY + RUNTIME_RESIDENT_READ` (a media engine's host memory
  is the spec's stated `ram_gb`, charged directly against `MemAvailable` with
  no text-engine margin), with a compensating invariant that every config
  engine is known to `serving`.
- seam 4 second slice, `tts` (RTF): sized and rendered for real, from stated
  numbers only, one engine name for the whole TTS ladder (Piper / Kokoro /
  StyleTTS). A TTS unit's card peak is its stated working set — **no VAE
  spike**, which is the image engine's — and a `cpu_only` unit (a Piper-class
  rung, d-01) claims no card at all; `disk_gb` is the disk claim and the
  stated `ram_gb` is the host claim, charged directly against `MemAvailable`.
  Width 1, no window, no KV cache, no offload. The launch spec carries only
  stated values (the `hf_cache` weights directory, the port, the operator's
  `serve_args`); mcgyvr ships no TTS server image or shell binary, so
  `units.<unit>.image` is required, the pasted-shell rendering is refused, the
  compose service mounts the weights directory at its own absolute path, and
  a cpu_only unit carries no GPU reservation (`gpu` is the `-1` "no card"
  sentinel, `alternate` short-circuits before the card comparison, and
  `_sequence_on_one_card` skips it). `KNOWN_ENGINES = (llama.cpp, vllm,
  diffusers, tts)`; `config.py`'s `engine` enum gained `tts`. The media path
  is generalized behind `MEDIA_ENGINES` and a shared `_media_service`; the two
  `ModelSpec` bridges (capability row and `launch` block) both carry
  `cpu_only`. Review-round ruling: the text-engine refusal margin
  (`REFUSAL_RAM_HEADROOM_GB`) is a *text-engine* figure, so `hold_together`
  applies it only when a launch spec holds a text engine — a media-only spec
  sums its stated host memory with no margin (this also corrects diffusers
  co-residency). Deferred: the `/v1/models` healthcheck on co-resident
  non-cpu media units (shared with diffusers), the `-1` sentinel's
  classification, `declared_models` dropping `cpu_only` on an `hf_cache`-only
  override, and refusing a `cpu_only` row that states a non-zero `vram_gb`
  (`records/review-seam4-tts.md`).
- seam 4 third and final slice, `comfyui` (image + video workflows): sized and
  rendered for real, from stated numbers only, reusing the generalized media
  path (`MEDIA_ENGINES`, `_sized_media`, `_media_service`) reviewed in the TTS
  slice — no new logic. A ComfyUI unit's card peak is its stated working set,
  with **no VAE spike** (ComfyUI tiles its decode, c-04); `disk_gb` and the
  stated `ram_gb` are the disk and host claims, charged directly against
  `MemAvailable`. Width 1, no window, no KV cache, no offload. The launch spec
  carries only stated values (the `hf_cache` weights directory, the port, the
  operator's `serve_args`); `units.<unit>.image` is required, the pasted-shell
  rendering is refused, and compose mounts the weights directory at its own
  absolute path. `KNOWN_ENGINES = (llama.cpp, vllm, diffusers, tts, comfyui)`;
  `config.py`'s `engine` enum gained `comfyui`. **Seam 4 (serving → diffusers /
  ComfyUI / TTS) is now closed**; seam 6 cost units stay open but unshipped
  (no media row has a measurement yet).
- P2 first increment (gate output posture flip, done — product `b9d59596`): a
  structural output check whose validator is missing (``ToolUnavailableError``)
  is now *inconclusive* — a rejection — never a skipped environment issue that
  accepts, flipping the P1 posture recorded above. ``InconclusiveRung.exit_code``
  is optional (``None`` = the required tool never ran; an ``int`` = it ran and
  its answer is unreadable). The output-checks rung records the rung in both
  channels — the ``inconclusive`` list that decides the verdict, and the
  rendered sentence in ``environment_issues`` for older readers — mirroring the
  adapter rung's ``ToolFailedError`` handling. ``safety_pass`` / ``asr_wer`` /
  ``grounded`` remain stubs that raise; a contract declaring one now *rejects*
  until the validator lands. Reviewed (`records/review-p2-missing-validator.md`).

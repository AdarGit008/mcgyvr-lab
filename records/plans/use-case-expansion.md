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
  rung + contract params). Increment 5 (serving) next.
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

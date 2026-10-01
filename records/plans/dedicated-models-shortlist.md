# Dedicated-model shortlist

The candidate ladders for the new use cases, cheapest rung first. **Permissive
default, non-commercial opt-in** — the owner's ruling from the use-case plan.

**Licenses here are as researched, not verified.** Every license must be read on
the HF model card at download time (the filename is not evidence, and a license
can change between research and binding). Where the shortlist is uncertain it
says so.

## chat and agent share the text ladder

`chat` (raw endpoint) and `agent` (gated tasks) both serve general LLMs on the
existing llama.cpp/vLLM backends — the difference is the gate, not the model.
Non-coder throughout.

| rung | model | license | why |
|---|---|---|---|
| 1 | Phi-4-mini (3.8B) | MIT | smallest useful general assistant; agent tool-calling |
| 2 | Qwen3 8B / 14B (non-coder) | Apache 2.0 | safest all-round default |
| 3 | Gemma 3 12B / 27B | Gemma (verify) | multimodal, 128K context |
| 4 | Llama 4 Scout | Llama (verify) | 10M context, research/explore |

Long-context rungs are sized by the KV dials, not by weights alone (e-01, e-02).
Sampling is per-use-case: `chat` warm, `agent` greedy (e-03).

## image

| rung | model | license | why |
|---|---|---|---|
| 1 | SDXL-base-1.0 | OpenRAIL | fast workhorse, lowest VRAM floor |
| 2 | SD 3.5 Medium / Large | Stability Community (verify $1M cap) | middle weight, best prompt adherence per GB |
| 3 | FLUX.1-schnell | Apache 2.0 | 4-step distilled, quality leader, permissive |
| 4 | FLUX.2 [klein] 4B | Apache 2.0 (4B weights) | ~2.6 GB GGUF Q4, fits 8 GB, 4 steps |

Opt-in: FLUX.1-dev (non-commercial). Sizing dials are c-01 through c-03; the
capability row is `seconds_per_image` (media-capability-shape.md).

## video

| rung | model | license | why |
|---|---|---|---|
| 1 | LTX-Video 0.9.5 (2B) | verify | fastest that fits a 12 GB card |
| 2 | Wan 2.2 (5B) | Apache 2.0 | quality leader on 24 GB, permissive |
| 3 | HunyuanVideo 1.5 (8.3B) | verify (commercial needs a check) | 8.3B DiT, consumer-GPU targeted |
| 4 | LTX-2.3 (~22B DiT) | verify | audio + video in one pass |

Sizing dials are c-04 (frame budget, spatio-temporal tiling) plus the image
dials. Capability row is `seconds_per_clip` at a frame budget.

## tts

| rung | model | license | why |
|---|---|---|---|
| 1 | Piper | MIT | CPU, faster than realtime, cheapest rung |
| 2 | Kokoro-82M | Apache 2.0 | near-human quality, permissive |
| 3 | StyleTTS 2 | MIT | permissive quality fallback |

Opt-in: XTTS v2 (CPML) and F5-TTS (CC-BY-NC) — both non-commercial, so they are
off the default ladder for a monetising creator. Sizing dials are d-01 through
d-03; the gate is ASR word-error-rate against the transcript (d-02).

## What "dedicated per use case" means here

Every model above is a **use-case specialist, not a coder**: no `*-coder`
checkpoint enters a chat, agent or media rung, and no general model enters the
coding ladder. The coding vertical keeps its existing `*-coder` table untouched.

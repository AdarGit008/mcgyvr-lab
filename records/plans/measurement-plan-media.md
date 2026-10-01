# Measurement plan — media and context backends

What to read once the rigs serve the new backends. The concept entries name the
mechanism; this names the readback and the card class. Numbers land in
`records/measurements/`, never in `okf/` or a config.

## Principle

- **Read, don't label** — sum the tensor table (GGUF header / `config.json`
  `quantization_config`) before planning around a checkpoint
  (`must-read/touching-models`).
- **Estimates by card class** (6 / 12 / 24 GB), replaced by the user's own
  reading after the first read (the-split).
- **A claim with no artifact is not a finding** (`must-read/always`).

## Per modality

### diffusion (image)

Cost unit: `seconds_per_image` at a stated resolution.

- weights: per-component sum — text encoder, denoiser, VAE — from the tensor
  table (c-03), not the filename.
- VAE decode spike: peak VRAM at decode (c-01), read from the engine's own
  peak line, not from card occupancy.
- steps: the checkpoint's distilled step count and guidance value (c-02).
- ladder map: model → card class by the denoiser's *resident* size (c-03).

### video

Cost unit: `seconds_per_clip` at a stated frame budget.

- temporal compression (÷N) and the frame budget that fits a card (c-04).
- FP8 on/off and the offload granularity the row actually launched with.

### tts

Cost unit: `rtf` at a stated sample rate.

- RTF from the engine's own log — seconds of audio per second of compute — not
  from token rate (d-01).
- sample rate, and the ASR gate run at that rate (d-02).
- `cpu_only` marker for Piper-class rungs (d-01).

### chat / agent (long context)

Cost unit: `throughput_tok_s` (existing) plus KV bytes at a stated context.

- KV cache dtype and bytes-per-token (e-01); the engine's own KV / max-concurrency
  line is the only width readback (`config/vllm`).
- offload readback: the engine's offloaded-parameter line, never RAM figures
  (`config/vllm`).
- sampling defaults measured per use case — `chat` warm, `agent` greedy (e-03).

## Gate evidence (separate from cost)

- `asr_wer`: whisper transcription WER against the transcript (d-02), measured
  on a held-out transcript set, at the output's sample rate.
- `media_valid` / `safety_pass`: validators and classifier, measured as
  false-accept / false-reject on a labeled set — a gate is judged by its errors,
  not by a single pass.

## Order

Read the header of every candidate *before* any download or bind; then measure
cost per card class; then measure gate evidence last, because a gate that never
rejects is not a gate.

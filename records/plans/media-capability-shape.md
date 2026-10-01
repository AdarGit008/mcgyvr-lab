# Media capability-table shape

How `data/capability-table.json` extends to the media modalities, when the
media use case reaches the product. P0 design note; the schema lands with the
implementation, not here.

## What it keeps

The existing table's contract: **estimates by card class**, one card read per
class; a row is a cost to serve, never a quality figure; the user's own reading
replaces an estimate after the first read (the-split). A media row keeps the
same contract with a modality-appropriate cost unit.

## Cost unit per modality

| modality | cost unit | why |
|---|---|---|
| text (today) | `throughput_tok_s` | decode is bandwidth over bytes per token |
| image | `seconds_per_image` at a resolution | the run is steps × per-step forward, then one VAE decode |
| video | `seconds_per_clip` at a frame budget | frames × resolution is the cliff; time is the honest unit |
| tts | `rtf` (real-time factor) | speech cost is seconds-of-audio per second-of-compute |

## Row fields, media

Beyond the text row's `id / family / params_b / quant / weights_gb /
vram_gb_working / backend / caveat`, a media row adds:

- image: `resolution` (the row was read at), `steps` (distilled count),
  `weights_gb` as a per-component sum (text encoder, denoiser, VAE — c-03),
  `vae_decode_gb` (the decode spike — c-01).
- video: `frames`, `resolution`, `temporal_compress` (÷N — c-04).
- tts: `sample_rate_hz`, `rtf`, and a `cpu_only` marker (Piper-class models
  need no card — d-01).

## The gate hook is separate

Evidence kinds (`media_valid`, `safety_pass`, `asr_wer` — d-02) judge the
output, not the cost. Capability stays cost-only, exactly as the text table
"carries no quality figure."

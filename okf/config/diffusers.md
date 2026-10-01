# config — diffusers / ComfyUI

What each knob does, and what it does not do. Values are derived per rig and
per model, never copied from here. These backends do not serve today; this is
the reference the media use case will read when they do.

→ `okf/models/c-01` through `c-04` for the mechanisms these knobs move.

## `num_inference_steps` / `guidance_scale`

**The multiplier (c-02).** A full CFG model pays `steps × 2` forward passes; a
distilled few-step model (Flux schnell, FLUX.2 klein, SDXL-turbo/LCM) drops
`guidance_scale` to 1 and `steps` to about 4. **The same output size can cost an
order of magnitude apart on this pair alone** — pick a distilled checkpoint
before reaching for a bigger card.

**Guidance is not quality.** A distilled model at `guidance_scale=1` is the
design point; raising guidance on one buys nothing and can wash the image.

## `enable_attention_slicing`

**Slices the attention computation to cut peak memory**, trading a little
latency. A memory dial, not a quality one — turn it on before offloading, turn
it off only when the card has room to spare.

## `enable_model_cpu_offload` vs `enable_sequential_cpu_offload`

**Component-level vs subcomponent-level offload (c-03).** `model_cpu_offload`
keeps one whole component resident at a time (denoiser on card, text encoder
and VAE paged from RAM). `sequential_cpu_offload` offloads everything,
subcomponent by subcomponent — the lowest VRAM floor and the slowest wall time.
**Sequential offload is a fallback, not a default:** it admits a model the card
otherwise refuses, and pays for it in latency.

## VAE slicing / tiling

**Caps the decode spike (c-01).** The VAE upscales latent to full-resolution
pixels once at the end; slicing decodes one image of a batch at a time, tiling
decodes one patch at a time. **Tiling is what keeps a large-resolution decode
inside a small card** — the spike, not the denoiser, is usually what OOMs last.

## Quantization (GGUF / FP8 / NF4)

**A dial on the denoiser's size, with a latency cost (c-03).** GGUF streams a
quantised denoiser from RAM; FP8/NF4 shrinks it on the card. **The VAE and text
encoder are usually left unquantised** — quantising the VAE visibly degrades
pixels.

## `max_sequence_length` (Flux)

**Prompt-encoding length.** The timestep-distilled variant caps it at 256; the
full model does not. A prompt longer than the cap is truncated, silently — match
the checkpoint to the prompt, or the image is not what was asked.

## ComfyUI `--lowvram`

**Streams weights from system RAM instead of holding them on the card.** Same
mechanism as sequential offload, at the engine level. Use it to run a model that
nearly fits; it is not a substitute for picking the right checkpoint.

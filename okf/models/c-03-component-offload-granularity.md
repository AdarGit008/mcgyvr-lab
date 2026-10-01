---
type: Concept
title: Text encoder, denoiser and VAE offload separately
description: The three components have different duty cycles; offload and quantize each on its own schedule.
tags: [local-ai, media, diffusion]
---

# Text encoder, denoiser and VAE offload separately

A text-to-image stack is three separable components with different duty cycles:
the text encoder (CLIP; T5-XXL in SD 3.5 and Flux) runs once per prompt, the
denoiser (U-Net or DiT) runs every step, and the VAE runs once at the end.
Offload the once-per-run components to RAM; keep the per-step denoiser
resident. Offload granularity — whole component, layer group, layer — sets the
VRAM floor, and GGUF/FP8/NF4 quantization is the independent dial on the
denoiser's size.

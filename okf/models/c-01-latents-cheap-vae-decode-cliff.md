---
type: Concept
title: Latents are cheap; the VAE decode is the cliff
description: Generation runs in a ÷8 latent space; the one-shot VAE decode to pixels is the full-resolution VRAM spike.
tags: [local-ai, media, diffusion]
---

# Latents are cheap; the VAE decode is the cliff

Diffusion runs on a compressed latent (a 1024px image is a 128×128 latent, ÷8
per side), so all the denoising happens on a small tensor. The VAE decoder is a
separate full-resolution network that upscales latent to pixels once at the
end — a one-shot VRAM spike that can exceed the denoiser's footprint at large
resolutions. Tile or slice the VAE to cap that spike; the denoiser never needs
full-resolution activations.

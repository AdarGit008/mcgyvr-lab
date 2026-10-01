---
type: Concept
title: Video compresses time too; tile over space and time
description: Video latents compress time as well as space; frame budget is the cliff, and spatio-temporal tiling decodes in stitched tiles.
tags: [local-ai, media, diffusion]
---

# Video compresses time too; tile over space and time

Video diffusion adds a temporal compression (÷N in time) to the spatial ÷8, so
the latent is (frames/N, h/8, w/8). The frame budget is the VRAM cliff: more
frames is more latent tokens, which multiplies attention. Spatio-temporal
tiling encodes and decodes in overlapping tiles across space and time and
stitches them with blending, so a long or high-resolution clip never
materializes whole. The image dials (`c-02`, `c-03`) all still apply, scaled by
the temporal axis.

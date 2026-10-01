---
type: Concept
title: The KV cache is the context cliff
description: At long context the KV cache — bytes per token × context length — dominates VRAM, not the weights.
tags: [local-ai, models, context]
---

# The KV cache is the context cliff

At long context the KV cache, not the weights, is what fills the card: it grows
bytes-per-token × context length and is read every decode step. A model that
fits comfortably at short context can spill at long context without the weights
moving at all. Context length is not free just because the checkpoint fits.

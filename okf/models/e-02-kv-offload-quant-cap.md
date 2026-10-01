---
type: Concept
title: Offload, quantize, or cap the KV cache
description: The long-context dials are offload to DRAM, quantization, or a sliding-window cap.
tags: [local-ai, models, context]
---

# Offload, quantize, or cap the KV cache

Three dials move the context cliff. Offload the cache to system DRAM and page
it in per step (weights stay resident). Quantize it — FP8/Q8 halves the cache
and runs attention in the quantized domain. Or cap it with sliding-window
attention on architectures that never grow the full cache. The three are one
lever set, and a long-context rung is sized by them together.

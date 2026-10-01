---
type: Concept
title: Steps and guidance are a multiplier, not a setting
description: Cost is steps × forward passes per step; distilled few-step models collapse the multiplier to a handful.
tags: [local-ai, media, diffusion]
---

# Steps and guidance are a multiplier, not a setting

Cost is steps × forward passes per step. Classifier-free guidance runs two
forward passes per step (conditional and unconditional); a full 25–50-step CFG
model pays that multiplier every step. A distilled few-step model (Flux schnell,
FLUX.2 klein, SDXL-turbo/LCM) drops guidance to one pass and steps to about
four, collapsing the multiplier. The same output size can cost an order of
magnitude apart on this dial alone.

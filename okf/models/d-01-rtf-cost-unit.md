---
type: Concept
title: RTF, not tokens, is the cost unit
description: Speech cost is the real-time factor — seconds of audio per second of compute; tok/s is only a proxy.
tags: [local-ai, media, speech]
---

# RTF, not tokens, is the cost unit

Speech cost is the real-time factor: seconds of audio produced per second of
compute. RTF below 1 is faster than realtime and therefore streamable. Tokens
per second is only a proxy — a vocoder pipeline and an end-to-end model can show
the same token rate and very different audio-per-second — so size a TTS rung by
RTF at the target sample rate, not by token throughput.

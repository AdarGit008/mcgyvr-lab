---
type: Concept
title: Stream by chunking; clone by embedding
description: Streaming latency is time-to-first-chunk; cloning is a reference embedding, not a retrain.
tags: [local-ai, media, speech]
---

# Stream by chunking; clone by embedding

Streaming is chunking: split the text, synthesize each chunk, emit it, so
time-to-first-chunk — not total synthesis time — is the latency that matters.
Voice cloning is conditioning on a short reference embedding (a few seconds of
audio), not a retrain: it is zero-shot, so a cloned voice is a cheap input, not
a new checkpoint.

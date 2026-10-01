---
type: Concept
title: Vocoder or E2E; the gate is ASR against the transcript
description: The contract target is known text, so ASR word-error-rate against it is the deterministic gate.
tags: [local-ai, media, speech]
---

# Vocoder or E2E; the gate is ASR against the transcript

A VITS-style pipeline splits synthesis into phoneme→mel→vocoder (small,
CPU-friendly, Piper); an end-to-end model is one network (quality, Kokoro).
The mcgyvr-shaped fact is the gate: the contract target is the transcript —
known text — so an ASR pass that measures word-error-rate against it judges the
output deterministically. It is the one media gate that needs no classifier and
no human, and it exists because the input text is what the contract asked for.

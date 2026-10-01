---
type: Concept
title: Chat samples warmer than coding
description: Coding wants greedy/low temperature; chat wants temperature and top-p — a per-use-case default, not a global.
tags: [local-ai, models, context]
---

# Chat samples warmer than coding

The two use cases want different decoding. Coding is judged by a deterministic
gate and wants greedy or low-temperature sampling — one right answer. Chat
wants diversity: temperature and top-p up. This is a per-use-case worker-facing
default, not a global constant; a coding-tuned default applied to chat produces
stiff, repetitive replies, and the reverse spends determinism the gate relies
on.

# config — TTS engines

What each knob does, and what it does not do. Values are derived per rig and
per model, never copied from here. These engines do not serve today; this is
the reference the media use case will read when they do.

→ `okf/models/d-01` through `d-03` for the mechanisms these knobs move.

## Chunk size (streaming)

**Sets time-to-first-chunk, not total time (d-03).** Text is split, each chunk
is synthesised and emitted. A smaller chunk starts speech sooner and can sound
less natural at the seams; a larger chunk is more natural and starts later.
**Streaming latency is measured to the first chunk, so tune this against the
use case, not against throughput.**

## Sample rate

**The contract target and the gate must agree (d-02).** XTTS v2 is 24 kHz;
Piper and Kokoro ship at 22.05/24 kHz depending on the voice. **The ASR gate
transcribes the output, so the ASR model must be run at the output's rate** — a
mismatch reads as a worse word-error-rate, which is a false rejection, not a bad
voice.

## Voice reference clip (cloning)

**A conditioning input, not a retrain (d-03).** A few seconds of reference
audio (~6 s for XTTS v2) produces a speaker embedding the model conditions on;
zero-shot. **A cloned voice is a cheap input** — changing it costs the clip, not
a new checkpoint.

## CPU vs GPU

**A VITS pipeline runs on CPU; an end-to-end model wants a card (d-01, d-02).**
Piper-class models synthesise on CPU faster than realtime. **Size the rung by
RTF, not by token rate**, and mark a CPU-only rung so the ladder does not charge
it card time it does not use.

## Streaming vs batch

**Streaming emits chunk by chunk; batch synthesises the whole text then emits.**
Batch is simpler and yields the cleanest prosody; streaming is the only mode
with a useful time-to-first-chunk. **Pick the mode from the consumer** — a
harness that plays audio as it arrives wants streaming, everything else wants
batch.

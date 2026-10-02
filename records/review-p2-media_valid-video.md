# Review — P2 media_valid video slice

Round delegated to `code-reviewer` over the media_valid-video working tree on
`lab/use-case-axis` (product commit `3e0d0203`). Verdict: **REQUEST CHANGES**
— one crash on truncated WEBM and one recursion hazard. Both fixed; dispositions
below.

## Findings and disposition

| # | sev | finding | disposition |
|---|---|---|---|
| 1 | crit | truncated WEBM (Segment size present, payload short) raised an uncaught `IndexError`/`struct.error` through `media_valid` — the clamp removal was only half the fix | **fixed** — a Segment-fits guard (`segment_payload + segment_size > len(data)` → `truncated`) before the walk; `_webm()[:17]` / `[:25]` cases added |
| 2 | med | recursive `find_duration` overflowed the stack on a deeply-nested pathological file | **fixed** — rewritten as an explicit-stack iterative walk (no recursion) |
| 3 | med | the truncated-WEBM case (`[:16]`) cut before the Segment size byte and never reached the overrun path | **fixed** — `[:17]` / `[:25]` added |
| 4 | low | many negative branches untested (MP4 extended box, mvhd v1, missing moov/mdat/mvhd, WEBM duration<=0, AVI microsec_per_frame==0, mid-chunk overrun) | **partially fixed** — MP4-no-mdath, AVI-zero-rate, WEBM-duration-zero added; the rest deferred (recorded) |

## Deferred (recorded, not blocking)

- MP4 `size==1` extended box, `size==0` to-EOF box, `mvhd` version 1 (refused as
  "not version 0"), `mvhd` < 20 bytes, `timescale==0`-with-nonzero-duration —
  untested negative branches; the box walk is bounds-safe, so these are
  coverage gaps rather than correctness risks.
- WEBM Duration element ≠ 4 bytes, no-Segment — untested; the code paths exist.
- AVI missing/short `avih`, mid-chunk overrun (only RIFF-size mismatch tested).

## What was clean

MP4 box walk is correct and bounds-safe (`size==1`/`size==0`/overrun). EBML vint
decode is correct (marker-bit clearing only for size, ID length ≤ 4, size length
≤ 8). AVI is correct (RIFF-size match, odd-size pad, hdrl→avih, the two
`avih` fields). The two conductor fixes — Segment size `0x8c` (12) and the clamp
removal — are correct in intent; the missing guard is now added. `import struct`
is stdlib, no new module, and every numeric literal lives inside a function
body, so `output.py` stays "holds no number that sizes or judges". This closes
seam 3's `media_valid` deepening across image, audio and video.

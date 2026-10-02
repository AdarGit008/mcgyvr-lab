# Review — P2 media_valid audio slice

Round delegated to `code-reviewer` over the media_valid-audio working tree on
`lab/use-case-axis` (product commit `e2a94497`). Verdict: **REQUEST CHANGES**
— the MP3 path never checked structural completeness (a bare valid frame header
passed), and two shared docstrings overclaimed. All fixed; dispositions below.

## Findings and disposition

| # | sev | finding | disposition |
|---|---|---|---|
| 1 | med | `_mp3_findings` accepted a valid frame header without verifying the first frame's body fits, so a header-only MP3 passed (undercut the "cannot fake a header" guarantee) | **fixed** — first-frame byte length computed from version/layer/bitrate/sample-rate/padding and refused `truncated` when it overruns the file; truncated-MP3 fixture added |
| 2 | med | module + `_audio_findings` docstrings claimed duration + structural completeness for ALL audio, overclaiming MP3 and OGG | **fixed** — narrowed to per-format truth (duration for WAV/FLAC/MP3; page structure only for OGG, duration deferred); `_PREFIXES` comment also narrowed |
| 3 | low | ID3v2.2 (`data[3] == 2`) uses a 3-byte non-syncsafe tag size, misread as 4-byte syncsafe | **fixed** — v2.2 reads `data[6:9]` big-endian; v2.3/v2.4 keep the 4-byte syncsafe read |
| 4 | low | OGG check stops at `27 + page_segments` without summing the lacing values | **deferred** — the docstring is honest ("only the page structure is checked"); record only |

## Deferred (recorded, not blocking)

- OGG duration (needs Vorbis/Opus identification-header parse for the sample
  rate + last-page granule position) — later pass.
- OGG lacing-value sum / CRC check — later pass, if "structurally complete"
  is meant to be stronger for OGG.
- WAV chunk walk accepts 1–7 trailing bytes after the last chunk when fmt/data
  were already seen (the RIFF-size match catches most real truncations).

## What was clean

FLAC STREAMINFO bit arithmetic (`[18:26]` big-endian, 20-bit sample rate, 36-bit
total samples) is exact; WAV RIFF-size match, chunk walk with odd-size padding,
and `byte_rate == 0` refusal are correct; MP3's reserved/invalid header checks
correctly refuse "free format" (`bitrate_index == 0`). The conductor's earlier
removal of the dead `sample_rate_hz`/`duration` computation reads clean — the
MP3 check now computes the frame length (a real decision) and never a numeric
duration it would discard. Architecture held: every offset/table lives inside a
function body, so `output.py` stays "holds no number that sizes or judges", and
no new module.

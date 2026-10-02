# Review — seam 4 TTS slice

Round delegated to `code-reviewer` over the TTS-engine working tree on
`lab/use-case-axis` (product commit `7da3fca0`). Verdict: **APPROVE** — one
medium finding (text-margin bleed in `hold_together`) fixed; the rest triaged.

## Findings and disposition

| # | sev | finding | disposition |
|---|---|---|---|
| 1 | med | `hold_together` re-applied the text-engine `REFUSAL_RAM_HEADROOM_GB` (2.0 GiB) to media units' stated host memory in multi-unit specs — a media-only spec over-refused by 2 GiB | **fixed** — the margin applies only when a spec holds a text engine; a media-only spec sums its stated `ram_gb` directly, no margin. Tests added for both the fits and the still-refuses cases |
| 2 | med | `_sequence_on_one_card` writes the text-engine `/v1/models` healthcheck on non-cpu media units (pre-existing diffusers behavior); a co-resident media pair would hang at `service_healthy` | **deferred** — shared with the diffusers slice, out of scope for the cpu_only slice |
| 3 | low | `gpu = -1` sentinel is undocumented and unclassified; `mcgyvr emit` prints `gpu -1` for a Piper unit | **deferred** — inline in a function body (not a module-level numeric), and the `Unit.cpu_only` doc names the meaning |
| 4 | low | `declared_models` full-replacement precedence can drop `cpu_only` (an `hf_cache`-only media unit overrides a shipped Piper row's marker) | **deferred** — no media row ships yet, so it cannot fire; note before the first Piper row ships |
| 5 | low | `_sized_media` silently discards a stated `vram_gb` when `cpu_only=True` rather than refusing the contradiction | **deferred** — cross-validation belongs at the capability-table loader when a cpu_only row ships |
| 6 | low | diffusers `unit_for` refusal wording regressed from "HuggingFace cache" to the generic "weights directory" | **accepted** — `hf_cache` is the operator-stated weights directory across media engines, so the generic wording is the accurate one |

## What was clean

`cpu_only` handled end-to-end: `fit` zeroes peak/headroom/card-free and skips
the card check; `unit_for` assigns `gpu=-1` and skips `_roomiest_gpu`, so a
card-less scan is accepted; `_media_service` omits the `deploy` reservation;
`alternate` short-circuits on `cpu_only` before the gpu comparison;
`_sequence_on_one_card` skips cpu_only units; `launch_specs`/`hold_together`
bucket them under `gpu=-1` with `vram=0`, so they never sum against a card.
Both `ModelSpec` bridges carry `cpu_only`, each pinned by a test. The
`KNOWN_ENGINES == engine-enum` lockstep invariant holds. Diffusers `_sized_media`
behavior is preserved exactly. No invented number (the only new literal is the
inline `-1` sentinel).

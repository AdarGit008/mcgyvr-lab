# Review — P1 increments 5a/5b/5c-1/5c-2 (and the increment-4 tail)

Round delegated to `code-reviewer` over commits `5e03e4d3..75194010` on
`lab/use-case-axis`. Verdict: **CHANGES REQUESTED** — one functional regression
in the emit/wake path (co-residency) and one docstring/behaviour contradiction
(gate stubs). Both fixed; the rest triaged below.

## Findings and disposition

| # | sev | finding | disposition |
|---|---|---|---|
| 1 | high | resident-first sizing made the orchestrator and ladder emit as mutually-exclusive alternatives (`_card_free_gb` `min()` double-counted the claim) | **fixed** — `Unit.resident_claim_gb` marks the orchestrator; `_card_free_gb` uses the full card when the set includes a resident; regression test added |
| 2 | high | `safety_pass`/`asr_wer`/`grounded` docstrings claimed "inconclusive/rejection" while the code accepts via environment issue | **fixed** — docstrings now state the P1 posture (accept as a legible env-issue hole; P2 must make a missing validator inconclusive) |
| 3 | med | `_remaining_scan` broke the `Vram` invariant `total == used + free + reserved` | **fixed** — the claim moves from `free_mib` to `used_mib` |
| 4 | med | `users` width fallback applied to a hosted orchestrator in the ladder | **fixed** — gated on `_local(orchestrator_name)` |
| 5 | low | contract.py circular-import comment named the wrong module | **fixed** |
| 6 | low | `media_valid` finding carried an absolute sandbox path | **fixed** — `media_valid(path, kind, label)` quotes the repo-relative target |
| 7 | low | `local_orchestrator` decision not wired to serving (chat/hybrid "provision nothing" unenforced at emit) | **deferred** — acknowledged incremental; recorded in the plan |
| 8 | low | MP4 `ftyp` accepted without a plausible box size | **fixed** — box size must be `0`/`1`/`8..len(data)`; test data corrected |
| 9 | low | "written width wins over `users`" untested | **fixed** — precedence test added |

## What was clean

Seam invariants hold (`serving` below, `contract`/`orchestrator` above, both
imports enforced); `parse_pinned` prose short-circuit correct; `_remaining_scan`
GiB↔MiB math exact; the output-check rung runs every declared check so one
unwired validator cannot hide another's finding.

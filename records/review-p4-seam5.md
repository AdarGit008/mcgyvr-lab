# Review — P4 packaging + Seam 5 (worker bundle per use case)

Round delegated to `code-reviewer` over product commits
`b8c33827..c47c3a01` on `lab/use-case-axis` (then the review-fix
`2007dd0f`). Verdict: **APPROVE** — no Critical; one Medium (the single-user
flag computed and dropped) and three Low findings, all addressed.

## Findings and disposition

| # | sev | finding | disposition |
|---|---|---|---|
| 1 | med | `LocalOrchestrator.width` / `.flag_single_user` were computed but never read — the "single-user flagged, not refused" half of the ruling was dropped | **fixed** — `init` now surfaces a decision line when a local-only non-chat install serves one user (`initialize.py`) |
| 2 | low | two `deployment` defaults: schema `hybrid` vs init's chat→local-only | **fixed** — `_deployment_default` documents the split: the schema default is the safe value for a hand-written config; only init writes local-only for a fresh chat install |
| 3 | low | use-case vocabulary spelled in three places (catalog data, config choices, CLI choices) | **fixed** — a catalog test pins `config.SCHEMA`'s `use_case` choices to the catalog's use-case names |
| 4 | low | `build()` docstring did not document `use_case`/`deployment` | **fixed** — documented |

## What was clean

The ruling is centralized for the *provision* boolean (`Config.provisions_local_orchestrator`) while `serving.units_for`, `capacity.py` and `pool.py` each keep the credential/width detail they own, and all three gate the `users` width fallback on the same boolean — so the three never disagree and none crosses the seam (the decision lives in shared `config.py`; `orchestrator/local.py` is deleted and removed from `ABOVE_THE_SEAM`). The no-cap default (`max_output_tokens=None`) threads through `proposer_for` and `reviewer_for` with the stale comment removed. The bundle refactor is tight: one `_BUNDLES` registry, `Bundle.key`, chat→`None`, agent/media-gen→`UNMEASURED` bundles under the byte ceiling. The two removed constants left `numbers.json` and `numbers_coverage.json` with no stale entries, and `mcgyvr.docgen --check` passes with `SETUP.md` carrying the two new keys.

Full gate green: pytest, `ruff check`, `ruff format --check`, `mypy`, `mcgyvr.docgen --check`.

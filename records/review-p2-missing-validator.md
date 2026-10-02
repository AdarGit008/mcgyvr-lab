# Review — P2 missing-validator posture flip

Round delegated to `code-reviewer` over the working tree on `lab/use-case-axis`
(product commit `b9d59596`). Verdict: **REQUEST CHANGES** — two stale prose
passages that still described the pre-flip posture; the code itself was
correct and complete. Both fixed, plus two suggestions applied; dispositions
below.

## Findings and disposition

| # | sev | finding | disposition |
|---|---|---|---|
| 1 | med | `runner.py` inline comment above the output branch still said an unwired validator "records an environment issue" | **fixed** — now says "records an inconclusive rung — a rejection" |
| 2 | med | `runner.py` module docstring's blanket rule "a tool not installed is an environment issue, not a rejection" is now false for the output-checks rung | **fixed** — carved out the missing-*validator* exception (inconclusive, rejects) |
| 3 | low | `InconclusiveRung` first docstring paragraph read as if it described only the crashed-tool case | **fixed** — reworded to name both shapes up front |
| 4 | low | the `None`-branch rendered sentence was only pinned by substring, not by the flip wording | **fixed** — test now asserts `is inconclusive` / `not available` / no `skipped` |

## What was clean

The flip is complete end-to-end: `OutputChecks.run` builds an `InconclusiveRung`
with `exit_code=None`; `Gate.run` folds it into `inconclusive`; `GateResult.accepted`
already gates on `not inconclusive`, so nothing else had to change for the
rejection to take effect. `exit_code: int | None = None` is safe — no production
code does arithmetic or formatting on `rung.exit_code`, and every rendering goes
through `str(rung)`. The circular-import avoidance (`TYPE_CHECKING` annotation +
function-local lazy import) matches the `typecheck.py` precedent, so `output.py`
gains no top-level `runner` import. The adapter rung (`ToolFailedError`) and the
output rung (`ToolUnavailableError`) now share one currency, and `environment_issues`
is kept as the rendered sentence for older readers.

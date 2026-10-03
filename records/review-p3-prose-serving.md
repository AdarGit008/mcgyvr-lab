# Review — P3 third increment (the prose-aware serving path)

Round delegated to `code-reviewer` over the prose-serving working tree on
`lab/use-case-axis` (product commit `b8c33827`). Verdict: **REQUEST CHANGES** —
no Critical; one Important (a missing test at the harness-facing delivery seam)
plus three suggestions. Addressed below.

## Findings and disposition

| # | sev | finding | disposition |
|---|---|---|---|
| 1 | med | the prose branch of `cli._report_climb` (report.answer, skip `_commit`, return 0) had no test — the drive tests stop at `worker_attempt` and the result tests only cover serialization | **fixed** — `test_a_prose_delivery_reports_the_answer_and_touches_no_file` drives `_report_climb` with a hand-built `Delivered` carrying a prose `Accepted`, and asserts code 0, outcome accepted, `report.answer` populated, and no file placed/committed |
| 2 | low | cli.py uses `("prose", "media_artifact")` literals while drive.py imports the constants | **accepted** — matches cli.py's existing `!= "whole_file"` literal and avoids a cli → worker.reply import; not worth blocking |
| 3 | low | the "no verifier for prose" behavior is not pinned — the prose drive test passes no reviewer, so `verifier is None` flows through the default `reviewer is None` path, not the `prose` predicate | **accepted** — the predicate is exercised in the code, and a reviewer-configured prose test would add setup weight for a branch already covered by reading |
| 4 | low | media_artifact is treated identically to prose in the drive | **accepted/noted** — consistent with the parser; to revisit when a media-gen task type lands (whether media_valid/asr_wer run over the staged request text vs an engine-written artifact) |
| 5 | low | the prose accepted row keeps the `passed` journal verdict rather than a delivery annotation (`committed`/`not_committed`) | **accepted** — correct, there is no commit/delivery for a raw-text answer |

## What was clean

The whole_file path is byte-for-byte untouched: `judge_draw`'s prose
short-circuit is additive, `_cleaned` is gated by `tidying and not prose`, and
the verifier is `None if prose or reviewer is None`. `gate_prose_workspace` is
correctly scoped to the four structural output-evidence kinds via
`output_checks_for`, accepts with an empty `GateResult()` for chat, and
propagates `findings`/`environment_issues`/`inconclusive` faithfully — so a
missing `safety-classifier` still rejects (inconclusive), never reads clean.
The agent-gate test stubs `safety_pass` at the module name `_run_one` resolves
at call time. `RunResult.answer` serializes through `asdict`/`write` with no
schema to update, and `report.outcome` is already "accepted" before the branch,
so the result file reads `accepted` with the answer populated.

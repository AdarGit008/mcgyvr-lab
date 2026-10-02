# Review — P2 validators slice (safety_pass / asr_wer / grounded)

Round delegated to `code-reviewer` over the validators working tree on
`lab/use-case-axis` (product commit `7d3c5609`). Verdict: **APPROVE** — no
Critical; two Important (operator-facing accuracy + a robustness gap) and
several suggestions, addressed below.

## Findings and disposition

| # | sev | finding | disposition |
|---|---|---|---|
| 1 | med | `asr_wer` invokes `whisper` but carried `ToolUnavailableError`/`ToolFailedError` tool name `"whisper-asr"` — the operator would be told to install a binary that does not exist | **fixed** — both raise sites and the matching test now use `"whisper"` |
| 2 | med | `subprocess.run` in both validators omitted `timeout`; whisper on a large artifact is the long-running case | **deferred** — the git/acceptance rungs also omit it, and skip-vs-reject on timeout is a deliberate policy to rule on; recorded |
| 3 | low | `_first_line` did not clip stderr, so a long first line became unbounded `detail` | **fixed** — clips to 200 chars, mirroring `adapter._first_complaint` |
| 4 | low | `grounded` docstring had a loose causal link ("deterministic … so never reports clean over no bar") and "unreadable bytes refused by name" was misleading | **fixed** — rephrased |
| 5 | low | `_run_one` `wer_threshold is None` → `ValueError` untested (unreachable through the loader) | **accepted** — mirrors the existing unknown-kind `ValueError`; not added |
| 6 | low | sentence split naive (`[.!?\\n]+` splits "Dr. Smith"); `[0]` never matches; source substring matches "alphabetical" | **accepted** — documented deterministic structural check |

## Deferred (recorded, not blocking)

- A timeout on the two new subprocess invocations, and the policy for a timed-out
  validator (skip = env-issue, like `typecheck`, vs reject = inconclusive). The
  reviewer's guidance: reject is the safe direction but must be deliberate.
- WER is unbounded above 1.0 (denominator is `len(reference)`, never
  `len(hypothesis)`), so `wer_threshold == 1.0` is not a ceiling — note on
  threshold semantics for the ASR vertical's use of the value.

## What was clean

Levenshtein DP is exact (hand-traced against all five vectors); returncode
semantics match the ruling; `_first_line` handles the bytes/str split;
`isinstance(exc, ToolUnavailableError)` discrimination is exact (siblings, no
subclassing); no circular import; `output.py` stays "holds no number that sizes
or judges"; subprocess arg lists are fixed (no shell, no injection). 18 new
tests cover both returncode branches, the ToolUnavailable/ToolFailed paths, the
WER math, and the inconclusive-with-exit-code integration.

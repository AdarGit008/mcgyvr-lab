# Review — P3 second increment (prose carries no output cap)

Round delegated to `code-reviewer` over the no-cap working tree on
`lab/use-case-axis` (product commit `e2d9af54`). Verdict: **REQUEST CHANGES** —
no Critical; one Important scope note (the orchestrator half of the ruling) and
two user-facing doc over-claims, plus three suggestions. Addressed below.

## Findings and disposition

| # | sev | finding | disposition |
|---|---|---|---|
| 1 | med | the ruling names two uncapped carriers — "prose (chat/agent) *and* the orchestrator" — but the change only uncaps the contract path; `delegate.py` `ORCHESTRATOR_OUTPUT_TOKENS` and `verify.py` `REVIEW_OUTPUT_TOKENS` still build `Request` with hard int caps | **deferred** — those are internal structured dispatches (a proposal, a review verdict), not the chat/agent prose path P3 is about; the no-cap half for the orchestrator/verifier is recorded for P4, when the local orchestrator is wired |
| 2 | med | `contract.py` `LIMITS_FIELDS["max_output_tokens"]` doc still said "Declare it for any task type a model executes" | **fixed** — "any whole_file task type"; raw-text carries no cap and declares nothing |
| 3 | med | `docgen.py` step-2 prose said "A contract a model executes must declare `limits.max_output_tokens`" | **fixed** — whole_file only; prose/media_artifact is uncapped |
| 4 | low | `contract.py` module comment near `output_cap` over-claimed "refuse a model contract that declares none" | **fixed** — whole_file only |
| 5 | low | `check_contract_fits`'s `cap=None` sentinel docstring no longer told the whole story (now also means "uncapped") | **fixed** — docstring names the uncapped case |
| 6 | low | telemetry rows now carry `max_output_tokens: null` for uncapped replies, inviting a coercion next to the absent-count rule | **fixed** — one-line comment distinguishes "cap issued (null = uncapped)" from "count the backend did not report" |

## What was clean

The `reply_cap` early return — `None` for an uncapped reply *before* the
rung's own `output_tokens` is consulted — is the subtle correctness point, and
it is pinned by a test that binds a rung declaring `output_tokens` and asserts
`None`, proving "uncapped stays uncapped wherever it runs". The OpenAI payload
omits `max_tokens` rather than sending null (the module's existing
"never present and null" convention). `overran_cap` and `_notes` distinguish
held / overran / uncapped-or-unreported with `bool | None`, and the
truncated-uncapped note blames the backend's own limit rather than a cap that
was not sent. The whole_file behavior is unchanged: the derived cap still
applies, and a whole_file contract with no declared cap is still refused.

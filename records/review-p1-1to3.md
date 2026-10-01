# Code Review — P1 generalize-the-core (commits 1–3)

Branch: `lab/use-case-axis` · Repo: `mcgyvr-lab-usecases/product` (read-only)
Reviewed: `97be405c`, `42652ba4`, `3a229f73`

## Review Summary

**Verdict:** APPROVE (all three commits) — with one latent parser inconsistency to fix before/with increment 5.

**Overview:** Three clean, well-scoped "P1 generalize the core" increments. Commit 1 adds the `use_case` axis as pure catalog data plus loader validation (schema v2). Commit 2 adds four structural evidence kinds as vocabulary-only data (`needs_commands: false`). Commit 3 adds the `prose` output schema as a true sibling to `whole_file` in the reply parser, prompt, and contract schema. All are genuinely data-first: no new code branch keys on a use-case name or evidence-kind name, and the tests pin that with a JSON-only invented type. The only substantive defect is latent, not currently reachable: `parse_pinned` does not short-circuit `prose` before its fence hunt.

Tests reviewed: yes — `tests/test_catalog.py`, `tests/test_worker_reply.py`, `tests/test_worker_prompt.py`, `tests/test_contract.py`; **179 passed**.
Build verified: yes (pytest run against `.venv`).
Security checked: yes — no untrusted-input or injection path in the new loader/parser branches; see Security notes.

---

## Commit 1 — `97be405c` "Carry the use case each task type belongs to, as catalog data"

**Verdict:** APPROVE

### Correctness
- Correct and complete. `data/task-catalog.json:28` declares the `use_cases` list; `src/mcgyvr/catalog.py:295-300` loads it; `catalog.py:334-338` adds `use_case` to `_require_keys`; `catalog.py:350-355` resolves the value against the declared set and rejects unknown values by name; `catalog.py:369-375` stores the resolved `UseCase` on `TaskType`.
- Schema version is bumped consistently in both places: `data/task-catalog.json:2` and `src/mcgyvr/catalog.py:46` (`SCHEMA_VERSION = 2`). No versioning bug.
- `_require_keys` uses `not entry.get(k)` (`catalog.py:334`), so an empty-string or missing `use_case` is rejected — consistent with the existing `name`/`starts_on`/`guarantee` fields. The missing-case test (`tests/test_catalog.py:test_a_missing_use_case_is_rejected`) and undeclared-case test both pass.

### Readability / Maintainability
- `UseCase` dataclass (`catalog.py:60-65`) mirrors the existing `Family`/`Evidence` shape; `doc` is read with a `""` default like the others. Consistent.
- `data/README.md` paragraph updated in lockstep with the `_purpose` string.

### Architecture — focus item 1 (data, not code branches)
- Confirmed. The loader is generic over the `use_cases` vocabulary: it builds a `by_use_case` map and resolves by name. There is **no** `if use_case == "coding"` branch anywhere in `src/` — `grep` shows `use_case`/`use_cases` are consumed only by `catalog.py` itself.
- Adding a task type under an existing use case is still a JSON-only edit: `tests/test_catalog.py:test_a_new_task_type_needs_no_code_change` was updated to include `"use_case": "coding"` and still passes without any code change.
- `Catalog.use_cases` and `TaskType.use_case` are populated but not yet read by routing/serving — which is correct staging for increments 4/5.

### Findings
- **[nit]** `src/mcgyvr/catalog.py:298-300` — the `use_cases` list is not checked for duplicate names; `by_use_case` dict construction is last-wins. This matches the existing (also-unchecked) `families` and `evidence_kinds` behavior, so it is not a regression, but a duplicate use-case name would silently shadow the earlier entry.
- **[minor/observation]** `chat`, `agent`, `media-gen` are declared but have zero task types; there is no orphan check. Intentional (the four axes are staged up front), but it means "a new use case needs only a JSON edit" is only exercised for `coding` today; the property will be re-proven when increments 4/5 add the first `chat`/`agent`/`media-gen` types.
- **[nit]** `tests/test_catalog.py:test_the_use_case_vocabulary_is_the_approved_four` hardcodes the four names. A *fifth* use case requires editing this test (not `catalog.py`), which is a deliberate guardrail but is worth knowing when the "approved" set is meant to grow.

---

## Commit 2 — `42652ba4` "Declare the media and agent evidence kinds in the catalog"

**Verdict:** APPROVE

### Correctness
- Four kinds added with only `needs_commands: false` and no `baseline` key: `data/task-catalog.json:87,92,97,102`. The loader defaults `baseline` to `"pass"` (`catalog.py:312-315`), which is exactly the intended semantics for a structural check with no baseline run.
- The one validation rule that could reject them — `baseline == "fail"` without `needs_commands` (`catalog.py:321-325`) — does not fire, because these default to `"pass"`.
- Test `tests/test_catalog.py:test_the_media_and_agent_evidence_kinds_are_declared` asserts presence, `needs_commands == False`, and `baseline == "pass"`.

### Architecture — focus item 2 (structural, no command emitted; gate stays the floor)
- Confirmed end-to-end:
  - **Contract assembly** — `contract.py:264` `_evidence_allowance` maps `needs_commands=False` → `STRUCTURAL_ALLOWANCE` (512), so a media/agent type would get the "nothing to run" cap, not `RUNNING_ALLOWANCE`.
  - `TaskType.needs_acceptance_commands` / `needs_demonstration_commands` (`catalog.py:118-135`) only become true for kinds with `needs_commands=True`. A type whose evidence is `["gate", "media_valid", …]` will **not** be forced to carry `acceptance`/`demonstration` commands. `contract.py:1219` / `1233` therefore never fire for these.
  - **Gate runner** — `src/mcgyvr/gate/runner.py` does not read `evidence_kinds` at all today; its rungs are injected, not derived from the catalog. So nothing emits a command for these kinds. The "gate makes them" wiring is correctly deferred to increment 4.
  - **Gate stays the floor** — enforced by `tests/test_catalog.py:test_every_entry_states_its_required_evidence`, which asserts `"gate" in kind.evidence_names` for every type. Unchanged and still passing.
  - **No name-keyed consumer breaks** — the only name-keyed evidence consumer is `orchestrator/decompose.py:106` (`_TYPE_CHECK = "type_check"`), and it only fills `type_check`, never the new kinds.

### Findings
- **[minor/observation — forward-looking]** `data/task-catalog.json:97` `asr_wer`'s doc says the gate stays "under the contract's threshold", but the contract schema (`src/mcgyvr/contract.py` `SCHEMA`) currently has **no field to state that threshold** (nor media dimensions/duration for `media_valid`). Increment 4/5 will need to add parameter plumbing (thresholds/specs) somewhere — either contract fields or per-evidence-kind parameters in the catalog. This commit correctly stops at vocabulary; the gap is flagged so it is not discovered mid-increment-4.
- **[nit]** No `schema_version` bump for commit 2 — correct, since it adds entries within the existing `evidence_kinds` shape and schema v2 (defined by commit 1) already covers it. Noting only to head off a reviewer who might expect one.

---

## Commit 3 — `3a229f73` "Add the prose output schema"

**Verdict:** APPROVE — with one latent parser inconsistency to fix before/with increment 5.

### Correctness
- `prose` joins the enum: `contract.py:561` `choices=("whole_file", "prose", "unified_diff")`; `test_contract.py:test_a_prose_output_schema_is_accepted` passes.
- Reply parser is a **true sibling**, not a smuggled special case:
  - `_unreadable` now accepts `PROSE` (`reply.py:329`), so an unsupported schema and an incomplete reply are still refused *before* any text is read.
  - The prose branch is an explicit, isolated early return after the completeness gate (`reply.py:465-466`): `return ParsedFile(content=_prose(text))`. No fence hunt, no `_carries_no_code`/`_refusal` refusal judgement — matching the commit's claim.
  - `_prose` (`reply.py:345-353`) only normalizes line endings and returns raw text; it does not append a trailing newline (prose is not a file). `whole_file` is untouched.
- Prompt: `_REPLY_INSTRUCTIONS[PROSE]` (`prompt.py:84-87`) gives a "plain prose, no fence, no code block, no preamble" instruction; `build_prompt` unsupported-schema error message updated to name both implemented shapes (`prompt.py:203-206`). `test_worker_prompt.py:test_a_prose_contract_gets_the_prose_instruction` passes.
- Tests: `test_worker_reply.py:test_prose_is_the_raw_text_not_a_fence_hunt` and `test_prose_still_refuses_an_incomplete_reply` both pass and verify exactly the two claims.

### Findings
- **[major, latent — fix before increment 5]** `src/mcgyvr/worker/reply.py:parse_pinned` does **not** short-circuit `prose`. With `response_schema is not None` and `output_schema == "prose"`, the function passes the `_unreadable` gate (`reply.py:530-532`) and then falls into `_fenced` (`reply.py:554`), which fence-hunts prose and returns `no-fenced-block` (or, worse, returns only an incidental fenced block inside the prose as "the answer"). This is not currently reachable — the production dispatch path calls `parse_reply`, not `parse_pinned` (`drive.py:849-854`; `parse_pinned` is only referenced by tests and the `runner.py` docstring) — so it is **not a P1 blocker**. But the reader's own contract ("reads both shapes, no caller has to know which arrived", `reply.py:499-503`) is now false for prose, and increment 5 (serving/harness) is where `parse_pinned`/`response_schema` wiring is expected to land. Fix: add `if output_schema == PROSE: return ParsedFile(content=_prose(text))` immediately after the `_unreadable` check in `parse_pinned`, plus a test mirroring the `parse_reply` prose tests.
- **[nit]** `_unreadable` now runs twice on the `whole_file` path — once at `reply.py:462` (added for the prose short-circuit) and again inside `_fenced` at `reply.py:383`. Harmless (idempotent), but worth a comment or a refactor so the double check reads as deliberate rather than accidental.
- **[nit]** The shared incomplete-reply message (`reply.py:335-340`) is `whole_file`-worded ("not known to be a whole file; a truncated file can parse cleanly…"). It still fires correctly for prose (semantics transfer), but the wording is now inaccurate for a prose answer and could confuse a reader of a chat/agent refusal log.
- **[minor/observation — forward-looking]** `prose` returns a `ParsedFile` whose docstring says "One file's complete content, safe to write" (`reply.py:266-276`), and the drive pipeline downstream of the parser (`drive.py:849` → `best_of` → gate → write `contract.target`) assumes file content that lands on disk. No chat/agent task type exists yet, so nothing is broken today, but increment 4/5 must add a prose-aware serving path that returns text to the harness instead of routing it through the file-write/gate pipeline. The parser sibling is correct; the surrounding pipeline is not yet prose-aware.

---

## Cross-cutting assessment (5 dimensions)

- **Correctness:** Each commit does exactly what it claims; validation, schema versioning, and parsing are correct. Tests verify the claims.
- **Readability/maintainability:** Excellent — every change is documented in the module docstrings and data `_purpose`/`_note` fields, and naming (`use_case`, `PROSE`, `_prose`) is consistent with project conventions.
- **Architecture:** Lays a clean foundation. The `use_case` axis and the new evidence kinds are pure catalog data with generic loaders; `prose` is a first-class output schema, not a branch. Increments 4/5 have a clear seam (catalog → contract loader → gate runner → serving) to build on.
- **Security:** No new untrusted-input surface. The catalog loader still parses only the shipped/local JSON and does `str()` conversions + dict lookups; `_prose` returns model text verbatim with no encoding/escaping. If a chat endpoint later renders prose into HTML, output encoding is the harness's responsibility — out of scope here but worth remembering for increment 5.
- **Performance:** No N+1, unbounded loops, or missing pagination. The only cost is the doubled `_unreadable` call on the `whole_file` path (negligible).

---

## What's Done Well

- The "data, not code" discipline is genuinely enforced, not asserted: `test_a_new_task_type_needs_no_code_change` drives an invented JSON-only type through the loader, and the `use_case` addition preserves it.
- `prose` is implemented as a sibling in the parser with the completeness/refusal split kept clean — the commit did not bolt prose handling into `_fenced` or the refusal logic.
- The new evidence kinds correctly carry `needs_commands: false`, which the *existing* `baseline == "fail"` validation and the `needs_*_commands` properties already understand, so the contract loader refuses no command for them with zero code change.
- Commit messages and inline docs precisely describe behavior and rationale, making the review tractable.

---

## Safe to build increments 4 + 5 on top? — YES, with two conditions

1. **Fix before increment 5:** the `parse_pinned` prose short-circuit (see the major finding under commit 3). It is a one-line fix plus a test; leaving it means the first prose contract that also pins a `response_schema` silently breaks.
2. **Plan for, in increment 4/5:** parameter plumbing for the structural evidence kinds (`asr_wer` threshold, `media_valid` dimensions/duration) — they are declared as vocabulary today but the contract schema has no field to state those parameters yet.

No other defect blocks building on these commits.

## Verification Story

- Tests reviewed: **yes** — `tests/test_catalog.py`, `tests/test_worker_reply.py`, `tests/test_worker_prompt.py`, `tests/test_contract.py`; 179 passed (`pytest -p no:cacheprovider`).
- Build verified: yes — test run in the project `.venv` (Python 3.12.3).
- Security checked: yes — no secrets in the diff, no new dependency, no untrusted-input parsing beyond the existing catalog loader; prose is returned unencoded (harness responsibility).

# Review — P3 first increment (chat + agent task types)

Round delegated to `code-reviewer` over the catalog working tree on
`lab/use-case-axis` (product commit `ac73519b`). Verdict: **REQUEST CHANGES** —
two Important (a loader null-handling regression and the unaccounted "format"
component of the agent gate), plus four suggestions. All addressed; the rest
triaged below.

## Findings and disposition

| # | sev | finding | disposition |
|---|---|---|---|
| 1 | high | `required_evidence: null` passed the `"required_evidence" not in entry` guard and then raised an unhandled `TypeError` (`'NoneType' object is not iterable`); `""` silently loaded as `()` | **fixed** — `isinstance(entry["required_evidence"], list)` after the absent-key check: absent is refused by name, an empty list (chat) is legal, null and any non-list are refused by name; null-case test added |
| 2 | med | the plan's agent gate is "grounded citations + safety + format", but the type declared only `["grounded", "safety_pass"]` and never named "format" | **fixed** — the agent guarantee/warrant/doc now state that the reply's format is the prose output protocol (raw text, not a file), so "format" is accounted for as the output schema rather than a separate evidence kind; recorded in the plan |
| 3 | low | test discriminator keyed on `kind.name == "chat"` rather than the use case | **fixed** — keyed on `kind.use_case.name == "chat"` |
| 4 | low | `test_the_chat_type_is_the_sole_ungated_type` overclaimed ("sole" is enforced by the neighbour test) | **fixed** — renamed `test_the_chat_type_is_ungated` |
| 5 | low | chat warrant opened with "structural —", which the catalog reserves for a gate-made check | **fixed** — dropped the prefix; chat's warrant states the vacuous case plainly |
| 6 | low | the missing-key test popped `required_evidence` from `format`, not from the entry the rule is about | **fixed** — pops from the `chat` entry |

## What was clean

The `gate` evidence-kind doc is the precise line of the change — it
distinguishes the `gate` *kind* (the deterministic code gate) from "the gate's
output-checks rung" (where `grounded`/`safety_pass`/`media_valid`/`asr_wer`
run), matching `gate/runner.py` and `drive.py:output_checks_for`. The relaxed
`test_every_entry_states_its_required_evidence` correctly encodes "gate ⟺
coding use case" and is not brittle for media-gen's later arrival. The
`test_contract.py` fixture change is keyed on `grounded in kind.evidence_names`
rather than a type name, so it covers any future grounded-requiring type. The
two new types follow "data, not code": no per-type branch, no consumer naming a
type, and the loader edit is the smallest possible absent-vs-empty distinction.

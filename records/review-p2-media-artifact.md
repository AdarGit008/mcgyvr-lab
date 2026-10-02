# Review — P2 media_artifact output schema (seam 2)

Round delegated to `code-reviewer` over the media_artifact working tree on
`lab/use-case-axis` (product commit `94017d62`). Verdict: **APPROVE** — no
Critical or Important; three suggestions, one applied.

## Findings and disposition

| # | sev | finding | disposition |
|---|---|---|---|
| 1 | low | `MEDIA_ARTIFACT` not re-exported from `worker/__init__.py` alongside `PROSE`/`WHOLE_FILE` | **fixed** — added to the import and `__all__` |
| 2 | low | `_prose` now serves two schemas; the name is narrower than its behaviour | **accepted** — reworded docstring ("the raw-text answer") suffices; a rename to `_raw_text` is cosmetic |
| 3 | low | the shared `incomplete-reply` message is `whole_file`-flavoured ("not known to be a whole file") though the guard also covers `prose`/`media_artifact` | **accepted** — pre-existing (already applied to `prose`) |

## What was clean

The enumeration is propagated everywhere it exists — module docstring,
`_unreadable`, `build_prompt` error, contract `Field.doc`+`choices`, and the
docgen-rendered `SKILL.md`. The short-circuit is written once as
`output_schema in (PROSE, MEDIA_ARTIFACT)` in both `parse_reply` and
`parse_pinned`, and the `response_schema is None` early-delegation path inherits
it. `_unreadable` stays the single shared refusal guard. New tests mirror the
`prose` tests 1:1 including the pinned-`response_schema` path. The byte-budget
bump (18_600 → 18_700) is honest — the actual body is 18,606 bytes, and the
comment attributes the growth to one enum choice + one doc clause. `docgen
--check` is clean.

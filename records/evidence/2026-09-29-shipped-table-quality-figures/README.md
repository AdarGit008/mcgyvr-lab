# The shipped table's quality figures, and the code that read them

The owner ruled that the product's shipped table carries no quality figure,
and that the lab keeps the readings. The product's pull request 543 took the
quality ladder out of `mcgyvr init`, and its pull request 544 takes every
quality key, benchmark reading and score text out of the shipped table and
out of the code. This record keeps, byte for byte, the product files that
held them, as they stood before each pull request.

Each file is filed under the product commit it was taken from, at its path in
the product, with `git show <commit>:<path>`:

- `aec85058` (`aec85058a556b7e2966867935da5c959fd04fa4b`) is the commit pull
  request 544 branched from.
- `4e2b01f1` (`4e2b01f10ede8962b967c18ad94673998c4e8dd7`) is the commit pull
  request 543 branched from.

| file in this record | sha256 | git blob |
|---|---|---|
| `aec85058/data/capability-table.json` | `01b51d5128f4d3ed6647ae906c122f6adf4f47ae18504eb195d78e619f2df5fb` | `a2ba99c3` |
| `aec85058/data/README.md` | `6e59d6139a081abeffdbc63e2a8f61fcf35ca381f665243e132b3d660e2141ad` | `3553ef9a` |
| `aec85058/data/task-catalog.json` | `8e048d2bedf28b1e22fba320e036c831e2e9cd06a77a588d80c137cbfd77c6eb` | `c4c25ac3` |
| `aec85058/src/mcgyvr/capability.py` | `4c662afa961d38c94269e50b2ffb259a1152fecd6e5da7760d0546f6e06cd6b3` | `08e74cbe` |
| `aec85058/tests/red_port/test_x03_capability_dimensions.py` | `35fa93042251a9e2c658e48848f5d1e4040b3e9c525eefb28d5fac17000f2d49` | `a384600f` |
| `4e2b01f1/src/mcgyvr/propose.py` | `468e68ccfb472bc2caf98f8fc1fd639d92b1dd5ca28375141d47275c9dbd65c4` | `5f2513bb` |
| `4e2b01f1/tests/test_propose.py` | `406931d5d48c44b436b7f13e026c30297ad455ce877e25310b43a2a95946f229` | `7a9e23e8` |
| `4e2b01f1/tests/test_initialize.py` | `2e83ef357e51a3f7dd20025ab10493acf3f82892ab0a7308fb5bb072e2514f0a` | `2f4c72a7` |

Each sha256 was taken of the copy and of the blob git gives for
`<commit>:<path>`, and the two agreed; `git hash-object` of each copy gives
the blob id above. The product's history keeps the same bytes: under the
lab's `product/`, `git show aec85058:data/capability-table.json` (and so on
for each row) prints them.

The table filed here is `schema_version` 2, the table as it stood after it
was keyed by card class. The table before that, `schema_version` 1, is in
`../2026-09-29-shipped-table-before-card-classes/`. The table at `4e2b01f1`,
which that commit's `propose.py` and tests read, differs from the one filed
here only in its `_purpose` sentence; every reading is the same.

## What pull request 543 removed

Pull request 543 (branch `init-binds-what-running-servers-list`) merged in
the product as `ae4cad42`. Its commit `5ef4233c` names the removed tests.

- `src/mcgyvr/propose.py`: the quality ladder, the fit, pull, spread and
  placement code, and `MIN_QUALITY_GAIN` with its rationale. By name, the
  module-level names at `4e2b01f1` that the merge no longer has:
  `MIN_QUALITY_GAIN`, `_serving_source`, `_ineligible_reason`, `_slower`,
  `_tie_reason`, `_best_of_equal_quality`, `_dominated_by`, `_fit_reason`,
  `_placement_reason`, `_reasons`, `_candidates`, `_spread_note`; and the
  `Rung` fields `quality`, `vram_gb`, `weights_gb` and `already_present`, with
  `Proposal.must_pull` and `Proposal.download_gb`. `propose()` no longer takes
  a table, a card size, a headroom or a quality gain.
- `tests/test_propose.py`, 30 tests:
  `test_a_twelve_gb_card_gets_a_ladder_that_does_not_invert`,
  `test_every_step_up_clears_the_measurable_separation_floor`,
  `test_the_worked_inversion_case_is_never_bound`,
  `test_a_dominated_model_names_what_beat_it`,
  `test_the_ceiling_is_never_dropped_for_sitting_close_to_a_cheaper_rung`,
  `test_a_model_is_never_eliminated_by_a_candidate_that_is_itself_dropped`,
  `test_at_equal_quality_the_faster_model_is_the_rung`,
  `test_throughput_is_not_borrowed_across_backends`,
  `test_a_six_gb_card_is_proposed_the_moe_quality_rung`,
  `test_the_moe_rung_is_bound_to_the_backend_it_was_measured_on`,
  `test_without_llama_server_the_moe_rung_is_withheld_and_explained`,
  `test_a_six_gb_card_still_gets_a_working_ladder`,
  `test_no_unmeasured_model_is_ever_bound`,
  `test_a_withheld_model_says_it_was_withheld_on_purpose`,
  `test_no_gpu_yields_an_empty_local_ladder_rather_than_an_error`,
  `test_a_card_too_small_for_anything_is_still_not_an_error`,
  `test_every_rung_states_fit_quality_and_presence`,
  `test_already_pulled_models_are_reported_as_such`,
  `test_what_must_be_pulled_is_named_with_its_size`,
  `test_presence_breaks_ties_without_overriding_the_gradient`,
  `test_headroom_is_respected_on_every_rung`,
  `test_a_remote_rig_yields_a_ladder_with_no_gpu_here`,
  `test_a_remote_rig_admits_only_what_it_reports_holding`,
  `test_an_unmeasured_model_is_not_admitted_by_being_served`,
  `test_no_gpu_and_only_local_backends_still_proposes_nothing`,
  `test_a_ladder_spanning_machines_says_it_may_be_inverted`,
  `test_one_machine_gets_no_inversion_warning`,
  `test_an_arbitrary_placement_says_it_was_arbitrary`,
  `test_a_sole_holder_is_not_reported_as_a_coin_toss`,
  `test_a_remote_fit_never_cites_this_machines_card`.
- `tests/test_initialize.py`, 3 tests:
  `test_the_small_rig_gets_the_moe_rung_written_into_the_file` (line 207),
  `test_a_table_figure_among_the_decisions_is_called_an_estimate` (line 327),
  `test_a_ladder_across_machines_is_flagged_as_possibly_inverted` (line 472).
  Two other tests of this file were renamed in the same commit, not
  removed: `test_tiers_are_named_by_role_locality_and_model` and
  `test_detection_still_reads_the_native_model_listing`.

## What pull request 544 removes

Pull request 544 (branch `the-shipped-table-carries-no-quality-figure`, head
`b6923b0576e45d8acff656ae34e787f17ce711bf`) makes the table
`schema_version` 3.

- `data/capability-table.json`: `schema_version` 2 and the whole
  `quality_metric` block; every row's `quality` list with every reading
  (`humaneval_plus_pass1`, `humaneval_pass1`, `backend`, `card_class`), and
  the empty lists of three rows; `invalid_measurements` (two rows under
  CAV-01, one under CAV-02) and `disputed_measurements` (one row, CAV-03);
  the summary, detail and consequence of CAV-01, CAV-02 and CAV-03 as they
  were, with their figures; the row notes it removed or reworded; the old
  third entry of `backends.ollama.limits`; the old detail of CON-05.
- `data/README.md` and `data/task-catalog.json`: several sentences were
  reworded, not only removed, so both are filed whole.
- `src/mcgyvr/capability.py`: the quality and dimension parts
  (`DIMENSION_FLOOR`, `_DIMENSION_BY_EVIDENCE`, `CapabilitySelectionError`,
  `dimension_for`, `select_for_task`, `Model.quality`, `Model.capabilities`,
  `is_measured`, `capability()`, `best_quality`, `best_throughput` and its
  docstring, `shipped_table()`), the module docstring's scalar and vector
  paragraphs, and the incident in the `fitting` docstring.
- `src/mcgyvr/cli.py`, `_capabilities`: the score column and the sort by
  quality. Not filed; it is `aec85058:src/mcgyvr/cli.py` lines 117 to 123
  (the sort by `best_quality` at line 117, the score text at lines 118 and
  119, the printed column at lines 121 to 123).
- `tests/red_port/test_x03_capability_dimensions.py`: the whole file.
- `tests/test_capability.py`, not filed; at `aec85058`:
  `test_unmeasured_models_are_never_proposed` (line 29),
  `test_moe_quality_is_reachable_on_a_small_card` (line 67),
  `test_invalid_measurements_are_not_read_as_quality` (line 80), and the old
  bodies of `test_marginal_fits_are_excluded` (line 43) and
  `test_headroom_is_absolute_not_proportional` (line 54).
- `tests/test_a_table_of_another_shape_is_refused_by_name.py`, not filed; at
  `aec85058`: `test_a_capability_score_that_is_not_a_number_is_refused_by_its_row`
  (line 432), `test_capabilities_given_as_a_list_is_refused_by_its_row`
  (line 443), and the cases for the quality-metric level and the three
  removed reading lists.

## Where the readings are

Line numbers are of the files in this record.

- `aec85058/data/capability-table.json`: `quality_metric`, lines 4 to 10;
  CAV-01, lines 17 to 21; CAV-02, lines 24 to 28; CAV-03, lines 31 to 35.
  The `quality` lists: `qwen2.5-coder:1.5b` lines 53 to 56, `qwen2.5-coder:3b`
  70 to 73, `qwen2.5-coder:7b` 87 to 90, `qwen2.5-coder:14b` 107 to 109,
  `yi-coder:9b` 125 to 127, `deepseek-coder-v2:16b` 141 to 143,
  `qwen3-coder-30b-a3b` 159 to 161; the empty lists at lines 180, 197 and
  212. `invalid_measurements` at lines 95 to 97, 113 to 115 and 166 to 168;
  `disputed_measurements` at lines 181 to 183. The row notes pull request 544
  removed or reworded are at lines 61, 78, 98, 116, 131, 147, 169, 187 and
  202; the ollama limit at line 224; the CON-05 detail at line 244.
- `aec85058/data/README.md`: the metric at lines 40 and 41; "What the table
  is not", lines 48 to 55; "Known-bad figures", lines 57 to 75, with the
  CAV-01 and CAV-02 figures at lines 65 and 69; the validation of the
  vocabulary against the table, lines 113 to 121.
- `aec85058/data/task-catalog.json`: the `warrant` texts at lines 125 and
  142.
- `aec85058/src/mcgyvr/capability.py`: the module docstring's scalar and
  vector paragraphs, lines 13 to 35; `DIMENSION_FLOOR`, lines 70 to 74;
  `_DIMENSION_BY_EVIDENCE`, lines 76 to 105; `CapabilitySelectionError`,
  lines 112 to 120; `Model` with its quality parts, lines 150 to 216;
  `fitting`, lines 237 to 254; the quality keys among the declared keys,
  lines 256 to 356; the reading of `humaneval_plus_pass1`, line 651;
  `shipped_table`, `dimension_for` and `select_for_task`, lines 679 to 792.
- `4e2b01f1/src/mcgyvr/propose.py`: the ladder's rules in the module
  docstring, lines 10 to 47, with the worked example's two quality figures at
  lines 15 and 16; `MIN_QUALITY_GAIN` and its rationale, lines 58 to 68.
- `4e2b01f1/tests/test_propose.py` reads the shipped table; its docstrings
  quote readings at lines 78, 121 and 186, and line 172 asserts a quality
  bound.
- `aec85058/tests/red_port/test_x03_capability_dimensions.py`: its scores
  are invented for its fixtures, not readings.

The copy of `tests/test_initialize.py` names the owner's machines and cards,
as the product's file did at that commit.

## One point for the lab to check

CAV-02 in `aec85058/data/capability-table.json` (line 26) states that a
server program resolved `qwen3-coder-30b-a3b` to "an F16 weight set (~18
GB), not a Q4 quant", and its detail (line 27) calls it "The F16 pull". The
row declares `params_b` 30 (line 152). The hand-over that asked for this
record flags that a 30-billion-parameter model at F16, two bytes a weight,
comes to about 60 GB, so the two words of that text do not agree. The same
text is in the `schema_version` 1 table of the earlier record, and
`4e2b01f1/tests/test_propose.py` line 186 repeats "F16". This record files
the text as it stood and does not settle it. The product's CAV-02 at the
head of pull request 544 no longer says F16 and keeps "~18 GB".

## How to read it

The readings are data points: what a named model, file and server program
did on a card of the named class. The table files some readings under
`invalid_measurements` and one under `disputed_measurements`, and its README
heads them "Known-bad figures", each with the harness caveat that gives its
reason (CAV-01, CAV-02, CAV-03). Those are the table's own words, kept as
written.

This record is not edited after it is filed. A later reading goes in a new
record beside it.

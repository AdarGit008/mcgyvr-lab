# mcgyvr-lab

Research, measurements and planning material moved out of
[AdarGit008/mcgyvr](https://github.com/AdarGit008/mcgyvr) so that repository's
root shows the product.

- Source: `AdarGit008/mcgyvr@b85945001f74c2b50533dfedabd5e59d10a5aa55`
  (main, the merge of pull request #474).
- Content: 320 files, byte for byte as they were at that commit, imported
  with `git archive`. History stays in the source repository.
- Paths are unchanged. A citation in mcgyvr such as
  `records/plans/sleep-wake.md` or `archive/docs/port-from-local-ai.md`
  resolves here at the same path.

## What stayed in mcgyvr

Everything under `records/`, `archive/`, `fleet-setup/` and `okf/` that is not
listed below is still in mcgyvr: its code or tests read it, or a data file
cites it. The pull request that moved these files lists each kept path with
the file and line that reads or cites it.

## Moved paths

A path ending in `/` moved as a whole directory.

```text
archive/docs/2026-09-02-srv1-kernel-arms-ARTIFACT-CONTRACT.md
archive/docs/2026-09-02-srv1-kernel-arms-RUN-ORDER.md
archive/docs/PORT-DOD-WRAP.md
archive/docs/README-2026-09-05.md
archive/docs/adoption-bar-prior-art-2026-08-10.md
archive/docs/archive/README.md
archive/docs/archive/claims/
archive/docs/archive/decisions-machinery/
archive/docs/archive/plans-302/
archive/docs/archive/sessions/lane/10/
archive/docs/archive/sessions/lane/103/
archive/docs/archive/sessions/lane/106/
archive/docs/archive/sessions/lane/109/
archive/docs/archive/sessions/lane/11/
archive/docs/archive/sessions/lane/112/
archive/docs/archive/sessions/lane/113/
archive/docs/archive/sessions/lane/114/
archive/docs/archive/sessions/lane/115/
archive/docs/archive/sessions/lane/117/
archive/docs/archive/sessions/lane/118/
archive/docs/archive/sessions/lane/12/
archive/docs/archive/sessions/lane/121/
archive/docs/archive/sessions/lane/123/
archive/docs/archive/sessions/lane/125/
archive/docs/archive/sessions/lane/129/
archive/docs/archive/sessions/lane/133/
archive/docs/archive/sessions/lane/14/
archive/docs/archive/sessions/lane/142/
archive/docs/archive/sessions/lane/144/
archive/docs/archive/sessions/lane/15/
archive/docs/archive/sessions/lane/150/
archive/docs/archive/sessions/lane/155/
archive/docs/archive/sessions/lane/161/
archive/docs/archive/sessions/lane/163/
archive/docs/archive/sessions/lane/164/
archive/docs/archive/sessions/lane/167/
archive/docs/archive/sessions/lane/172/
archive/docs/archive/sessions/lane/174/
archive/docs/archive/sessions/lane/175/
archive/docs/archive/sessions/lane/177/
archive/docs/archive/sessions/lane/178/
archive/docs/archive/sessions/lane/183/
archive/docs/archive/sessions/lane/184/
archive/docs/archive/sessions/lane/185/
archive/docs/archive/sessions/lane/187/
archive/docs/archive/sessions/lane/189/
archive/docs/archive/sessions/lane/197/
archive/docs/archive/sessions/lane/20/
archive/docs/archive/sessions/lane/200/
archive/docs/archive/sessions/lane/201/
archive/docs/archive/sessions/lane/21/
archive/docs/archive/sessions/lane/210/
archive/docs/archive/sessions/lane/212/
archive/docs/archive/sessions/lane/216/
archive/docs/archive/sessions/lane/217/
archive/docs/archive/sessions/lane/22/
archive/docs/archive/sessions/lane/220/
archive/docs/archive/sessions/lane/225/2026-08-10-153913-adar.md
archive/docs/archive/sessions/lane/225/2026-08-10-192024-adar.md
archive/docs/archive/sessions/lane/225/2026-08-10-bench-pilot-brief.md
archive/docs/archive/sessions/lane/225/2026-08-11-bench-campaign-t1-brief.md
archive/docs/archive/sessions/lane/225/2026-08-11-bench-probe-t2-brief.md
archive/docs/archive/sessions/lane/225/2026-08-11-f1-confirmatory-sweep-adar.md
archive/docs/archive/sessions/lane/225/2026-08-11-f1-responsiveness-adar.md
archive/docs/archive/sessions/lane/225/2026-08-11-f1-responsiveness-prereg.md
archive/docs/archive/sessions/lane/225/2026-08-11-f1-tranches-8-9-and-sweep-adar.md
archive/docs/archive/sessions/lane/225/2026-08-11-floor-band-f1-tranche-5-adar.md
archive/docs/archive/sessions/lane/225/2026-08-11-floor-band-f1-tranche-6-adar.md
archive/docs/archive/sessions/lane/225/2026-08-11-floor-band-f1-tranche-7-adar.md
archive/docs/archive/sessions/lane/225/2026-08-11-floor-unit-and-checker-parity-adar.md
archive/docs/archive/sessions/lane/225/2026-08-11-phase4-t1-adar.md
archive/docs/archive/sessions/lane/225/2026-08-11-phase4-t2-probe-adar.md
archive/docs/archive/sessions/lane/225/2026-08-11-scaffold-ablation-adar.md
archive/docs/archive/sessions/lane/225/2026-08-12-floor-band-f1-tranche-10-adar.md
archive/docs/archive/sessions/lane/225/2026-08-12-screen-and-denominator-adar.md
archive/docs/archive/sessions/lane/229/
archive/docs/archive/sessions/lane/23/
archive/docs/archive/sessions/lane/230/
archive/docs/archive/sessions/lane/231/
archive/docs/archive/sessions/lane/234/
archive/docs/archive/sessions/lane/235/
archive/docs/archive/sessions/lane/24/
archive/docs/archive/sessions/lane/240/
archive/docs/archive/sessions/lane/249/
archive/docs/archive/sessions/lane/25/
archive/docs/archive/sessions/lane/251/
archive/docs/archive/sessions/lane/252/
archive/docs/archive/sessions/lane/26/
archive/docs/archive/sessions/lane/261/
archive/docs/archive/sessions/lane/262/
archive/docs/archive/sessions/lane/265/
archive/docs/archive/sessions/lane/266/
archive/docs/archive/sessions/lane/268/
archive/docs/archive/sessions/lane/276/
archive/docs/archive/sessions/lane/282/
archive/docs/archive/sessions/lane/285/
archive/docs/archive/sessions/lane/286/2026-08-18-220000-claude.md
archive/docs/archive/sessions/lane/286/2026-08-19-093000-claude.md
archive/docs/archive/sessions/lane/286/2026-08-19-093100-claude.md
archive/docs/archive/sessions/lane/286/2026-08-19-124300-claude.md
archive/docs/archive/sessions/lane/286/2026-08-19-171500-claude.md
archive/docs/archive/sessions/lane/286/2026-08-20-045000-claude.md
archive/docs/archive/sessions/lane/286/2026-08-20-131600-claude.md
archive/docs/archive/sessions/lane/286/2026-08-21-225912-claude.md
archive/docs/archive/sessions/lane/286/2026-08-21-233000-claude.md
archive/docs/archive/sessions/lane/286/2026-08-22-010000-claude.md
archive/docs/archive/sessions/lane/286/2026-08-22-020000-claude.md
archive/docs/archive/sessions/lane/286/2026-08-22-030000-claude.md
archive/docs/archive/sessions/lane/286/2026-08-22-040000-claude.md
archive/docs/archive/sessions/lane/286/2026-08-22-050000-claude.md
archive/docs/archive/sessions/lane/286/2026-08-22-060000-claude.md
archive/docs/archive/sessions/lane/286/2026-08-22-150000-claude.md
archive/docs/archive/sessions/lane/286/2026-08-22-162359-claude.md
archive/docs/archive/sessions/lane/286/2026-08-22-190347-claude.md
archive/docs/archive/sessions/lane/286/2026-08-22-224943-claude.md
archive/docs/archive/sessions/lane/286/2026-08-23-001755-claude.md
archive/docs/archive/sessions/lane/286/2026-08-23-052241-claude.md
archive/docs/archive/sessions/lane/286/2026-08-23-082132-claude.md
archive/docs/archive/sessions/lane/286/2026-08-23-130134-claude.md
archive/docs/archive/sessions/lane/286/2026-08-23-141359-claude.md
archive/docs/archive/sessions/lane/286/2026-08-23-183000-claude.md
archive/docs/archive/sessions/lane/286/2026-08-24-180000-claude.md
archive/docs/archive/sessions/lane/286/2026-08-24-213000-claude.md
archive/docs/archive/sessions/lane/286/2026-08-24-230000-claude.md
archive/docs/archive/sessions/lane/286/2026-08-24-233000-claude.md
archive/docs/archive/sessions/lane/286/2026-08-24-235900-claude.md
archive/docs/archive/sessions/lane/286/2026-08-25-000500-claude.md
archive/docs/archive/sessions/lane/286/2026-08-25-060000-claude.md
archive/docs/archive/sessions/lane/287/
archive/docs/archive/sessions/lane/289/
archive/docs/archive/sessions/lane/291/
archive/docs/archive/sessions/lane/295/
archive/docs/archive/sessions/lane/299/
archive/docs/archive/sessions/lane/301/
archive/docs/archive/sessions/lane/304/
archive/docs/archive/sessions/lane/32/
archive/docs/archive/sessions/lane/36/
archive/docs/archive/sessions/lane/361/
archive/docs/archive/sessions/lane/365/
archive/docs/archive/sessions/lane/38/
archive/docs/archive/sessions/lane/43/
archive/docs/archive/sessions/lane/46/
archive/docs/archive/sessions/lane/47/
archive/docs/archive/sessions/lane/48/
archive/docs/archive/sessions/lane/49/
archive/docs/archive/sessions/lane/5/
archive/docs/archive/sessions/lane/50/
archive/docs/archive/sessions/lane/51/
archive/docs/archive/sessions/lane/52/
archive/docs/archive/sessions/lane/74/
archive/docs/archive/sessions/lane/8/
archive/docs/archive/sessions/lane/87/
archive/docs/archive/sessions/lane/9/
archive/docs/archive/sessions/lane/91/
archive/docs/bench-shape-prior-art-2026-08-11.md
archive/docs/bench-sourcing-2026-08-10.md
archive/docs/board-findings-2026-08-31.md
archive/docs/findings-table-2026-08-31.md
archive/docs/floor-audit-2026-08-09.md
archive/docs/four-lens-audit-2026-08-14.md
archive/docs/hybrid-orchestration-prior-art-2026-08-16.md
archive/docs/identifier-naming-prior-art-2026-08-15.md
archive/docs/identity-surface-2026-08-16.md
archive/docs/local-ai-review-2026-08-05.md
archive/docs/plans/
archive/docs/port-dod-majors-plan.md
archive/docs/port-from-local-ai.md
archive/docs/port-pressure-test-2026-08-29.md
archive/docs/portable-code-prior-art-2026-08-14.md
archive/docs/positive-control-candidates-2026-08-14.md
archive/docs/prior-art-review-2026-08-06.md
archive/docs/prior-art-summary-2026-08-06.pdf
archive/docs/prior-art-summary-2026-08-06.tex
archive/docs/problem-pool-prior-art-2026-08-07.md
archive/docs/serving-vllm-n32-plan-2026-08-31.md
archive/docs/test-witness-sweep-2026-08-07.md
archive/docs/unsloth-fine-tuning-review-2026-08-06.md
archive/docs/what-a-tune-may-train-on-2026-08-10.md
archive/run-request-2026-08-30-n1248.md
archive/src/
archive/tests/
archive/tools/
fleet-setup/REPORT-srv1.md
fleet-setup/REPORT-srv2.md
fleet-setup/REPORT.md
fleet-setup/digests-srv1.json.py
fleet-setup/evidence-srv1.json
fleet-setup/evidence-srv2.json
fleet-setup/evidence.json
fleet-setup/prompt-srv1.txt
fleet-setup/prompt-srv2.txt
fleet-setup/prompt.txt
fleet-setup/run-plan.md
records/plans/config-library.md
records/plans/fleet-identity.md
records/plans/fleet-shape/
records/plans/flexibility-campaign.md
records/plans/handoff.md
records/plans/kv-dtype-measurement-requirements-2026-09-11.md
records/plans/measuring-gaps-2026-09-10.md
records/plans/sleep-wake.md
records/plans/wake-timeout.md
```

## Later moves

The import above is one commit's files. Anything moved out of mcgyvr after it
is listed here, with the commit it came from, so no entry above is restated
and the 320-file count stays what it was.

### 2026-09-16 — srv1's superseded fleet lock records

- Source: `AdarGit008/mcgyvr@6022805c` (main), the commit the re-lock was
  assembled from.
- Content: 3 files, byte for byte, at the path they held in mcgyvr.
- Why: srv1's rig id changed, so `mcgyvr fleet lock` wrote srv1's three
  combination records afresh under `rig-3c89f35d…` and left the old
  directory behind. The lock tree keeps one source of truth; these are the
  2026-09-13 approvals it replaced, kept as data points, not deleted.
- They carry one field the current records do not: `card_steady_mib`
  (5430, 5094, 5602).

```text
records/fleet/rigs/rig-0f7fc6ae2bf6f8bbed8ed774507ef94a04d7f18a0f81b4d7761ce5ae81d03eeb/
```

### 2026-09-16 — the campaign logs that existed only on one machine

- Source: the working checkout of `AdarGit008/mcgyvr` at `b9578aaa` (main).
  These files were never tracked there: `.gitignore` ignores `*.log` outside
  `records/evidence/`, so they lived on the machine that ran the campaigns and
  nowhere else.
- Content: 487 files, byte for byte, at the paths they held in mcgyvr. 11 MB,
  all text — 479 plain, 6 JSON, 2 diffs.
- Why: owner ruling 2026-09-16, uncommitted measurements go to the lab.
  mcgyvr's own `.gitignore` states the principle these fall under — "lens 1:
  record the unrecoverable. A campaign log that lives on one laptop is exactly
  that" — and exempts `records/evidence/**/*.log` for it. These sit under
  `records/measurements/`, so the exemption never reached them. They are kept
  as data points; nothing here is a verdict on the runs that wrote them.
- The measurements these logs belong to are still in mcgyvr under the same
  campaign directories. Only the untracked logs moved.

```text
records/measurements/flexibility-2026-09-09/      201 files
records/measurements/measuring-gaps-2026-09-10/   145 files
records/measurements/fleet-gaps-2026-09-09/        92 files
records/measurements/fleet-identity-2026-09-11/    34 files
records/measurements/ram-headroom-2026-09-09/       7 files
records/measurements/quick-check-2026-09-15/        6 files
records/measurements/lock-fleets/                   2 files
```

### 2026-09-16 — the quick-check files that were untracked but not ignored

The earlier 2026-09-16 move swept files git *ignored*. These 21 are the
complement: untracked and un-ignored, so no ignore rule ever matched them and
the first sweep did not see them. They are the `.bench-py.stdout`,
`.bench-ts.stdout`, `.launch.txt` and `run.json` artifacts of the same
quick-check campaign, plus the campaign's own `drive.sh` and `summarise.py`.
Screened for credentials before publishing: the only matches were token
*counts* and a gate rung named `secrets`.

### 2026-09-17 — the prose nothing in mcgyvr reads

- Source: `AdarGit008/mcgyvr@1e9a47f1` (main).
- Content: 134 files, byte for byte, at the paths they held in mcgyvr:
  decision records, evidence and measurement write-ups, corpus and header
  READMEs, one plan, and one repository note.
- Why: owner ruling 2026-09-17, mcgyvr goes prose-light. A rule or guideline
  lives in mcgyvr's `okf/`; every other piece of prose that no code, test or
  packaging step opens lives here. The measurements these files describe
  (JSON, JSONL, TSV, logs, model output) stayed in mcgyvr under the same
  directories.
- A citation in mcgyvr reads `mcgyvr-lab/<path>`; a citation inside a data
  file was left as written and resolves here at the same path.
- Screened before publishing: no credentials; the addresses that appear are
  private-range and tailnet addresses mcgyvr's own source already prints.

```text
archive/docs/archive/decisions/0001-founding-scope-and-boundaries.md
archive/docs/archive/decisions/0002-merge-protection-on-the-default-branch.md
archive/docs/archive/decisions/0003-binding-names-carry-no-role.md
archive/docs/archive/decisions/0004-inherited-research-is-re-verified-before-it-is-adopted.md
archive/docs/archive/decisions/0005-gate-checks-never-run-target-code-on-the-host.md
archive/docs/archive/decisions/0006-the-type-checker-is-the-target-repositorys.md
archive/docs/archive/decisions/0007-dependency-signatures-come-from-the-index-not-from-a-model.md
archive/docs/archive/decisions/0008-sampling-breadth-is-policy-and-selection-is-the-first-gate-pass.md
archive/docs/archive/decisions/0009-output-discipline-is-a-cap-not-a-stop-sequence.md
archive/docs/archive/decisions/0010-environment-resolved-checks-run-in-the-sandbox.md
archive/docs/archive/decisions/0011-the-semantic-resolver-is-staged-not-installed.md
archive/docs/archive/decisions/0012-re-entry-is-refused-by-what-the-caller-holds.md
archive/docs/archive/decisions/0013-decomposition-is-api-tier-only.md
archive/docs/archive/decisions/0014-the-acceptance-boundary-is-never-mocked.md
archive/docs/archive/decisions/0015-a-failed-verifier-never-promotes.md
archive/docs/archive/decisions/0016-fixtures-capture-what-the-parser-reads.md
archive/docs/archive/decisions/0017-the-floor-is-the-product.md
archive/docs/archive/decisions/0018-one-bench-every-lever-and-the-whole-system.md
archive/docs/archive/decisions/0019-the-bar-is-a-reality-floor-and-a-per-lever-rule.md
archive/docs/archive/decisions/0020-retire-the-rulers.md
archive/docs/archive/decisions/0021-the-benchs-obligation-is-the-floor-unit.md
archive/docs/archive/decisions/0022-a-lever-is-never-a-difficulty-knob.md
archive/docs/archive/decisions/0023-difficulty-is-behaviour-count.md
archive/docs/archive/decisions/0024-comparable-measurements-come-from-one-rig-and-one-build.md
archive/docs/archive/decisions/0025-the-javascript-lint-bar-is-the-projects-and-it-mirrors-pythons.md
archive/docs/archive/decisions/0026-four-lenses-record-mutate-state-the-property-and-price-the-axes.md
archive/docs/archive/decisions/0027-run-identity-is-one-block-and-an-unreadable-field-is-a-refusal.md
archive/docs/archive/decisions/0028-a-routing-policy-is-adopted-only-if-it-is-inspectable-here-and-measured-here.md
archive/docs/archive/decisions/0029-the-gate-is-the-scorer-so-there-is-no-answer-to-extract.md
archive/docs/archive/decisions/0030-throughput-is-not-the-ceiling-and-the-serving-bench-is-already-in-the-table.md
archive/docs/archive/decisions/0031-the-pre-gate-heuristic-verifier-is-refuted-by-our-own-replies.md
archive/docs/archive/decisions/0032-a-round-boundary-is-drained-not-taken-and-the-pin-covers-the-bars-configuration.md
archive/docs/archive/decisions/0033-the-bar-the-prompt-and-the-weights-are-hashed-where-they-are-resolved.md
archive/docs/archive/decisions/0034-a-rung-that-cannot-say-what-bar-it-applied-is-a-refusal.md
archive/docs/archive/decisions/0035-the-bar-is-recorded-as-content-and-there-is-one-acceptance-ceiling.md
archive/docs/archive/decisions/0036-the-bare-word-bar-is-banned-adoption-bar-and-scoring-bar.md
archive/docs/archive/decisions/0037-a-finding-is-a-check-and-closing-without-fixing-is-a-dated-xfail.md
archive/docs/archive/decisions/0038-a-machine-has-no-role-and-the-question-approves-its-own-scope.md
archive/docs/archive/decisions/0039-a-serving-memory-declaration-is-bytes-not-a-fraction-of-the-card.md
archive/docs/archive/decisions/0040-a-placement-fraction-needs-an-engine-that-spills.md
archive/docs/archive/decisions/0041-placement-is-semantic-until-a-null-shows-it-neutral.md
archive/docs/archive/decisions/INDEX.md
archive/docs/archive/evidence-prose/2026-08-22-coresidency-feasibility/README.md
archive/docs/archive/evidence-prose/2026-08-23-phase0-refit/README.md
archive/docs/archive/evidence-prose/2026-08-23-sole-client-counters/README.md
archive/docs/archive/evidence-prose/2026-08-24-config-sweep/session-report-2026-08-24.md
archive/docs/archive/evidence-prose/2026-08-24-engine-sweep/CORRECTIONS.md
archive/docs/archive/evidence-prose/2026-08-24-engine-sweep/README.md
archive/docs/archive/evidence-prose/2026-08-24-knob-surface/README.md
archive/docs/archive/evidence-prose/2026-08-24-resolved-config/README.md
archive/docs/archive/evidence-prose/2026-08-25-moe-expert-offload/README.md
archive/docs/archive/evidence-prose/2026-08-25-moe-expert-offload/width-sweep/README.md
archive/docs/archive/evidence-prose/2026-08-26-capability-boundaries/README.md
archive/docs/archive/evidence-prose/2026-08-26-claim-verification/CLAIMS.md
archive/docs/archive/evidence-prose/2026-08-26-claim-verification/REPORT.md
archive/docs/archive/evidence-prose/2026-08-26-claim-verification/REVIEW-QUEUE.md
archive/docs/archive/evidence-prose/2026-08-26-claim-verification/srv1-findings.md
archive/docs/archive/evidence-prose/2026-08-26-claim-verification/srv1-llama-sweep-restore.md
archive/docs/archive/evidence-prose/2026-08-26-claim-verification/srv2-findings.md
archive/docs/archive/evidence-prose/README.md
archive/docs/archive/evidence-prose/bench-resolution-2026-08-14/norule.md
archive/docs/archive/evidence-prose/calibration-2026-08-19/README.md
archive/docs/archive/evidence-prose/calibration-2026-08-19/d7-sleep.aborted-run.README.md
archive/docs/archive/evidence-prose/calibration-2026-08-19/step0-gaps.md
archive/docs/archive/evidence-prose/calibration-2026-08-19/step0-readiness.md
archive/docs/archive/evidence-prose/calibration-2026-08-19/step1-review.md
archive/docs/archive/evidence-prose/gate-rescore-2026-08-15/findings.md
archive/docs/archive/evidence-prose/gate-rescore-2026-08-15/per-stratum.md
archive/docs/archive/evidence-prose/gate-rescore-2026-08-15/rescore-summaries.md
archive/docs/archive/evidence-prose/local-ai-2026-08-02/README.md
archive/docs/archive/evidence-prose/local-ai-2026-08-02/instrument/README.md
archive/docs/archive/evidence-prose/responsive-fraction-2026-08-15/per-stratum.md
archive/docs/archive/evidence-prose/responsive-fraction-2026-08-15/proposed-224-amendment.md
archive/docs/archive/evidence-prose/serving-surface-2026-08-18/README.md
archive/docs/archive/sessions/lane/225/2026-08-11-floor-band-f1-brief.md
archive/docs/bench-design-2026-08-10.md
archive/docs/srv1-kernel-arms-PLAN.md
archive/forensic-ollama/bench/bench-records.txt
archive/forensic-ollama/removed-lines.txt
archive/forensic-ollama/runner-cav01-excerpt.md
docs/conflicts.md
records/corpora/reach-2026-08-02/README.md
records/corpora/training-release-2026-08-10/README.md
records/corpora/worker-replies/README.md
records/evidence/2026-08-27-spec-decoding/README.md
records/evidence/2026-08-27-spec-decoding/store/README.md
records/evidence/2026-08-28-august-rollup/README.md
records/evidence/2026-08-28-august-rollup/drivers/BRIEF.md
records/evidence/2026-08-28-kat-coder/README.md
records/evidence/2026-08-28-mtp-ornith/README.md
records/evidence/2026-08-28-north-mini-code/README.md
records/evidence/2026-08-28-setup-selection/README.md
records/evidence/2026-09-02-srv1-kernel-arms/B2-CHECKPOINT.md
records/evidence/2026-09-02-srv1-kernel-arms/MMVQ-PATCH.md
records/headers/README.md
records/measurements/acceptance-ceiling-2026-08-17/README.md
records/measurements/breadth-2026-08-06/README.md
records/measurements/breadth-batch-b-2026-08-06/README.md
records/measurements/breadth-campaign-2026-08-06/README.md
records/measurements/finetune-pilot-2026-08-07/summary.md
records/measurements/fleet-gaps-2026-09-09/METHOD.md
records/measurements/fleet-gaps-2026-09-09/README.md
records/measurements/fleet-identity-2026-09-11/README.md
records/measurements/fleet-identity-prefill-2026-09-12/README.md
records/measurements/fleet-setup-2026-09-13/srv1/README.md
records/measurements/flexibility-2026-09-09/README.md
records/measurements/floor-probe-2026-08-09/README.md
records/measurements/jsts-bundle-2026-08-04/README.md
records/measurements/kv-dtype-2026-09-11/README.md
records/measurements/lidenburg-expert-cache-2026-09-13/README.md
records/measurements/lidenburg-expert-cache-2026-09-13/srv1-leverage-research.md
records/measurements/load-mode-2026-09-08/README.md
records/measurements/mbpp-plus-1.5b-2026-08-11/summary.md
records/measurements/mbpp-plus-3b-2026-08-10/summary.md
records/measurements/measuring-gaps-2026-09-10/README.md
records/measurements/measuring-gaps-2026-09-10/SPEC-run-mechanics.md
records/measurements/measuring-gaps-2026-09-10/live-state-before-teardown.md
records/measurements/pool-probe-2026-08-07/README.md
records/measurements/pool-sweep-14b-2026-08-07/README.md
records/measurements/pool-sweep-14b-cap2048-2026-08-08/README.md
records/measurements/pool-sweep-2026-08-07/README.md
records/measurements/pool-sweep-7b-batch67-2026-08-08/README.md
records/measurements/python-bundle-2026-08-07/README.md
records/measurements/ram-headroom-2026-09-09/README.md
records/measurements/reach-2026-08-03/README.md
records/measurements/reach-jsts-2026-08-03/README.md
records/measurements/serving-concurrency-2026-09-06/README.md
records/measurements/serving-sweep-2026-08-25/README.md
records/measurements/serving-sweep-2026-08-25/rig-reality-2026-08-25.md
records/measurements/srv1-ncmoe-sweep-2026-09-13/README.md
records/measurements/tokens-2026-08-03/README.md
records/measurements/vllm-sleep-2026-09-09/README.md
records/measurements/wake-2026-09-08/README.md
records/plans/fleet-identity-measurements-2026-09-11.md
```

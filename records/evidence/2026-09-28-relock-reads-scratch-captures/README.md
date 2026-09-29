# Scratch captures of the 2026-09-28 relock reads, filed after the fact

These seven files are copies, byte for byte, of files a later session found in
the scratch folder of the session that produced
`records/evidence/2026-09-28-relock-reads/`. They were not filed when that
record was made. A reviewer later found that the scratch folder still held
them, and the owner ruled that they are added to the lab as evidence, in a new
record beside the first one, because a record is not edited after it is
filed.

No neighbouring evidence folder in this repository carries a name for "a later
addition to an already-filed record" — none was found by search. This folder
is named `2026-09-28-relock-reads-scratch-captures`, following the plain
`<date>-<subject>` pattern the other evidence folders use.

## What this corrects

The first record's README says, of a refused read of srv2:

> That read left no artifact and no journal row, and no file in this
> repository records it: its time and the refusal quoted here are as the
> session that ran it wrote them into this file.

That is corrected by `post-stop-read-srv2.txt`, below: the first refused read
of srv2 did leave a capture — its own stdout, in the session's scratch folder
— and that capture is filed here. The first record's README is not edited;
this file stands beside it.

## The files

Each file below is the plain-text stdout of one command, copied unedited from
scratch. Times are as each file states them, UTC.

- **`post-stop-read-srv2.txt`** — sha256
  `bdab849bdfca865822457a5f6f4af270556c9782500ec5c8b41a26fe4a3df421`.
  The refused read of srv2 that the first record's README describes at
  22:08:10: the file's own refusal line reads `THIS MACHINE IS NOT THE
  DECLARED srv2 — pl1_uw: declared '4095000000', reads '65000000'`, the same
  text the first record quotes, with `rc=2`. The file's own timestamps run
  2026-09-28T22:08:10Z to 2026-09-28T22:08:12Z.

- **`pre-read-srv1-a-solo.txt`** — sha256
  `fd26701cbe22f3e6755bd93950a71b4cd4f7b5d77b359c13fdbad407f73e02fa`.
  One of the three reads before the refusal: a read of srv1 under fleet
  `a-solo`, `run_id=run-20260928T215734-218d6bf1`, the same run id the first
  record's table gives for the 21:57:34 srv1 row. The file's own timestamps
  run 2026-09-28T21:57:34Z to 21:57:37Z, `rc=0`.

- **`pre-read-srv1-live.txt`** — sha256
  `3ebab7f4330f88dd5108e028900877b7c359a7eac15359e994cb3bff10786d82`.
  A read of srv1 under the live fleet (no `--fleet` named in its output),
  `run_id=run-20260928T215755-ea68ba07`, the same run id the first record's
  table gives for the 21:57:55 srv1 row. The file's own timestamps run
  2026-09-28T21:57:55Z to 21:57:57Z, `rc=0`.

- **`pre-read-srv2.txt`** — sha256
  `4a5ee9002cb211c983d503e326953f1db1e12e7cfca5e3c98da006332e8350f5`.
  A read of srv2 under fleet `d-srv2-35b`,
  `run_id=run-20260928T215803-368360a8`, the same run id the first record's
  table gives for the 21:58:03 srv2 row. The file's own timestamps run
  2026-09-28T21:58:03Z to 21:58:06Z, `rc=0`.

- **`drive-srv2.txt`** — sha256
  `20575a9a3adc7b16d1e4c32a67138b3b65c3458f343dc7e9f01476933d2bc70a`.
  The output of the wrapper that drove srv2-01, the lock-fleets `new-cards`
  unit run named in `records/measurements/lock-fleets/new-cards/RUNS.md`. Its
  command line is `python -m mcgyvr.serving.run --host srv2 --campaign
  lock-fleets --step
  tools/runs/campaigns/lock-fleets/new-cards/01-new-cards-srv2-c1-srv2_35b_32k.sh
  --model /home/adaramir/models/moe/Qwen3.6-35B-A3B-UD-IQ3_XXS.gguf --parallel
  1 --ctx-per-slot 32768 --ubatch 512 --date 2026-09-28`. The wrapper's own
  markers read `START 2026-09-28T22:02:20Z` and `END 2026-09-28T22:07:10Z`,
  with `rc=3`; between them the unit is shown started at 22:02:22Z and exited
  1 at 22:07:09Z. These wrapper timestamps are close to, but not identical
  to, the driver-log times the first record quotes from
  `new-cards/RUNS.md` (22:02:22 to 22:07:09) — this file is filed as it
  stands, and the difference is not resolved here.

- **`journal-baseline.txt`** — sha256
  `ac168d6acb4104d65d06d2ba41948afba2036a427705605ec87f4db9abb2825f`.
  A list of journal file paths under the fleet journal with a line count
  beside each. It carries no timestamp of its own. Three of its rows name the
  same combination directories the first record's evidence comes from —
  `cmb-2a434290…`, `cmb-386eb5ca…`, and `cmb-bc6a1a75…` — with the line counts
  those files held at the time this list was made; the other two rows name
  combination directories the first record does not use.

- **`serve-down.txt`** — sha256
  `26da73552efa26e6bc6e1993c52bcfc49bcd241f5fb47151c98d2c67df2e03e1`.
  The gate-by-gate stdout of taking srv2's live unit down ahead of the
  `new-cards` window, run id `2026-09-28-live-srv2-serve-down-new-cards-takedown`
  — the same run id filed in
  `records/evidence/2026-09-28-live-srv2/serve-down.json` and its paired
  `.run.json`. The file's own markers read `START 2026-09-28T22:01:28Z` and
  `END 2026-09-28T22:01:50Z`; the paired `.run.json` gives `started_at` as
  2026-09-28T22:01:37Z. Both times are filed as each file states them, and
  the difference is not resolved here.

## Left out

`emit-check.txt`, `freeze.txt`, `make-check.txt`, and `make-guard.txt` were
also found in the same scratch folder and are not filed here.
`make-check.txt` and `make-guard.txt` are outputs of the lab's own gate
(`make check`, `make guard`), not of a door read or a door run, and the
existing record files no such gate output. `freeze.txt` (`srv2: 3 entries — 3
unit`) is the output of the campaign's own freeze step
(`plan.py freeze --use new-cards`), a planning step that does not read or
touch either machine; the same entry and unit counts are already in
`records/measurements/lock-fleets/new-cards/RUNS.md`. `emit-check.txt` is a
local compose-file emission ("Nothing was started") with no read of, or
command sent to, either machine.

## On the readings

The readings named above are data points. None is called invalid, a winner,
or ranked against another.

## Security

Every file above and every file left out was read for tokens, keys,
passwords, cookies, authorization headers, private key material, and full
environment dumps before being copied. None was found. Host names, machine
labels, card names, and paths of the owner's machines are not secrets and are
left as the files hold them.

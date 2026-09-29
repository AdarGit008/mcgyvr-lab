# Reads of srv1 and srv2 during the new-cards use of lock-fleets (2026-09-28)

These are the journal rows of the door reads taken around the `new-cards` use
(`records/measurements/lock-fleets/new-cards/`). Each row is copied as it was
written, line for line, from `~/.local/state/mcgyvr/journal/fleet/<combination>/`
into a folder of the same name here. Nothing was moved or edited, and the
journal itself was not touched. The readings are data points.

Every read ran as `python -m mcgyvr.serving.run read --host H [--fleet F]`. A
read starts, stops and leases nothing on the rig. Times are UTC.

| run id | at | host | command | filed in |
|---|---|---|---|---|
| `run-20260928T192156-b876857f` | 19:21:56 | srv1 | `read --host srv1 --fleet a-solo` | `cmb-2a434290…/rig.jsonl` |
| `run-20260928T192159-1e9021a2` | 19:21:59 | srv2 | `read --host srv2 --fleet d-srv2-35b` | `cmb-bc6a1a75…/rig.jsonl`, `unt-bf826b27….jsonl` |
| `run-20260928T215734-218d6bf1` | 21:57:34 | srv1 | `read --host srv1 --fleet a-solo` | `cmb-2a434290…/rig.jsonl` |
| `run-20260928T215755-ea68ba07` | 21:57:55 | srv1 | `read --host srv1` (the live fleet, `b-small@2026-09-16`) | `cmb-386eb5ca…/rig.jsonl` |
| `run-20260928T215803-368360a8` | 21:58:03 | srv2 | `read --host srv2 --fleet d-srv2-35b` | `cmb-bc6a1a75…/rig.jsonl`, `unt-bf826b27….jsonl` |
| `run-20260928T221000-e0800c69` | 22:10:00 | srv1 | `read --host srv1` (the live fleet, `b-small@2026-09-16`) | `cmb-386eb5ca…/rig.jsonl` |

The folder holds 10 rows: 6 in the three `rig.jsonl` files, one per read, and
4 in the unit file `unt-bf826b27….jsonl`, two per srv2 read.

- **`rig_id` and `observed_rig_id`.** Each of the 6 `rig.jsonl` rows carries
  both: the pinned rig id (`rig_id`) beside the id the reading names
  (`observed_rig_id`). The 4 unit-file rows carry
  `rig_id` and no `observed_rig_id`.
- **`setup`.** Each `--fleet` read's rows carry `locked=false` and a `setup`
  field, and the field names two folders:
  - the reads at 19:21:56 and 19:21:59 record
    `setup: /home/adaramir/claude/mcgyvr-lab/fleet-setup`;
  - the reads at 21:57:34 and 21:58:03 record
    `setup: /home/adaramir/claude/mcgyvr-lab-sessions/relock/lab/fleet-setup`.
- **The live-fleet reads** (21:57:55 and 22:10:00): their rows carry no `setup`
  and no `locked` field. No record here shows what setup or environment they
  were read under.

## What the rows read

- **srv1**, all four reads: `containers=none`, `gpu_procs=none`,
  `gpu_used_mib=1`, no unit. Kernel `7.0.0-34-generic`. `pl1_uw` 95000000 and
  `pl2_uw` 120000000. `uptime_since` 2026-09-27T19:17:37Z. Observed rig id
  `rig-b19063a9…`.
- **srv2**, both reads: one container (`6cc57657ff0f`) with `llama-server` at
  5626 MiB. The unit `srv2_35b_32k` was awake, with card_mib 5626 and restarts 0.
  Kernel `7.0.0-34-generic`. `pl1_uw` 4095000000 and `pl2_uw` 4095000000.
  `uptime_since` 2026-09-27T16:59:17Z. Observed rig id `rig-4cc155e5…`.

## srv2's power limit

- **4095000000** (`pl1_uw`): read at 21:58:03 (`run-20260928T215803-368360a8`,
  above). It was read again in the START marker of lock-fleets entry srv2-01,
  whose artifact records `started_at` 22:02:36.
- **65000000**: read in the END marker of srv2-01, whose artifact records
  `ended_at` 22:07:01
  (`records/evidence/2026-09-28-lock-fleets/new-cards-srv2-c1-srv2_35b_32k.json`,
  its `.RIGMOVED` file beside it). `uptime_since` is the same in both markers.
  The driver's log row for srv2-01 in
  `records/measurements/lock-fleets/new-cards/RUNS.md` gives 22:02:22 to
  22:07:09, the times the driver started and saw the end of the door command.
- A read of srv2 at 22:08:10 was refused, with nothing filed:
  `THIS MACHINE IS NOT THE DECLARED srv2 — pl1_uw: declared '4095000000', reads
  '65000000'`. That read left no artifact and no journal row, and no file in
  this repository records it: its time and the refusal quoted here are as the
  session that ran it wrote them into this file. Since then the door refuses
  srv2 against its declaration in `tools/runs/hosts.json`, which was not
  changed. No row for srv2 after 21:58:03 is in this folder.

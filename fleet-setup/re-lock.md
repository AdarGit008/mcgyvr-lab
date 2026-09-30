# Re-lock srv1 and srv2 under the card-slot rig identity

This is the lab's first job after the split. Everything in it is read-only on the
rigs until the last step writes the lock; the one thing that cannot be done
without the rigs is reading them, and those reads are marked **LIVE**.

## Why

Product PR #550 (merged as `4214aea7`, "a card in a different slot is a
different rig") made each card's PCI slot part of a rig's identity:
`mcgyvr.fleet.ids.rig_id` now hashes `gpu_slot` (device 0's slot) and, when the
rig holds cards beyond device 0, the `gpu_others` reading. A rig id read under
that spelling differs from every id pinned before it.

The ids pinned in `fleet-setup/fleet.yaml` predate that change, and predate the
card swap of 2026-09-26 (srv1 now holds two RTX 3060, srv2 a GTX 1660 SUPER):

- srv1 pinned `rig-3c89f35d83eb724f2b79f218a75c16768817ac83d2c00b740ae2236861ee1ae9`
- srv2 pinned `rig-cbe770b55841d616363165e38553a1c7c3768250df01ead1a255f0cbdef98455`

No fresh read names either id, so the lab's gate — whose lock-fleets tests
re-enact the lock against these records — is red until both rigs are re-locked
under the new spelling. The digests files are stale the same way:
`digests-srv1.json` still names srv1's old GTX 1660 SUPER, `digests-srv2.json`
srv2's old RTX 3060.

## What this is

A read-only re-derivation, then one write: read each rig through the door, take
the id its snapshot now names, refresh the rig blocks of
`fleet-setup/digests-<rig>.json` and the pins in `fleet-setup/fleet.yaml`, and
re-run `mcgyvr fleet lock` for the layout that fits the cards now
(`d-srv2-35b`).

## Steps

1. **(done by this PR)** `product/` is at `4214aea7`.

2. **LIVE — read each rig, read-only.** From the lab root, with
   `MCGYVR_RUN_ROOT` pointed at the lab so the read files into the lab's
   journal and never into `product/`:

   ```
   python -m mcgyvr.serving.run read --host srv1
   python -m mcgyvr.serving.run read --host srv2
   ```

   Each read's `rig.jsonl` row carries `observed_rig_id` and `snapshot`. A read
   starts, stops and leases nothing on the rig.

   Before reading srv2, re-check its power-limit declaration in
   `tools/runs/hosts.json`: on 2026-09-28 a read saw `pl1_uw` `4095000000` then
   `65000000`, and the door refused the later read as not the declared rig.

3. **Check the id.** Feed the snapshot's `k=v` lines to the helper; its `rig_id`
   must equal the read's `observed_rig_id`:

   ```
   uv run --no-sync python fleet-setup/re-derive-rig-id.py srv1 < snapshot.txt
   ```

4. **Refresh the digests rig blocks.** In `fleet-setup/digests-srv1.json` and
   `digests-srv2.json`, set `rig.rig_id` to the new id and `rig.fields.hardware`
   / `rig.fields.system` to the fresh snapshot's tokenized strings — the helper
   prints the exact block. srv1, with two cards, gains a `gpu_others` entry.

5. **Refresh `fleet-setup/fleet.yaml`.** Set each `rigs.<rig>.rig_id` to the new
   id.

6. **Re-lock.** `mcgyvr fleet lock` for the current layout, then confirm it
   wrote the fresh `records/fleet/rigs/<new-id>/cmb-*.json` directories:

   ```
   mcgyvr fleet lock --fleet fleet-setup/fleet.yaml \
     --policy fleet-setup/policy.yaml --evidence <evidence.json> --root .
   ```

   The lock for `d-srv2-35b` was started in the `new-cards` use
   (`records/measurements/lock-fleets/new-cards/`) and stopped after one of its
   three runs, so its evidence is incomplete; finish that use first if the lock
   refuses on missing evidence.

7. **Keep the superseded records.** The old `records/fleet/rigs/rig-3c89f35d…/`
   and `rig-cbe770b5…/` stay as data points, exactly as the 2026-09-16 re-lock
   kept `rig-0f7fc6ae…/`. The fleets made for the earlier cards already live in
   `fleet-setup/fleet.2026-09-28.yaml`.

8. **Run the lab gate** (`make check`) until it is green.

## Not carried here

The 2026-09-28 reads (`records/evidence/2026-09-28-relock-reads/`) named
`rig-b19063a9…` (srv1) and `rig-4cc155e5…` (srv2) under the pre-#550 spelling.
They are data points, not the new ids: the new ids hash `gpu_slot`.

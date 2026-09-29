# fleet-setup

## Which evidence file is which

Two versions of the fleet evidence file sit side by side here. Both are kept
byte for byte; neither replaces the other.

- `evidence.json` is the product's version, copied from the product at commit
  `ef12d3d3`. In the product's history it was last changed in commit
  `16bcd6d8` (committed 2026-09-16).
- `evidence.2026-09-13.json` is the version this lab held before that copy,
  under the name `evidence.json`. The lab imported it in commit `05fedf98`
  (committed 2026-09-15). It is the same file the product added in commit
  `7daebd79` (committed 2026-09-14) and removed in commit `4c73896d`, when that
  material moved to the lab.

## Which fleet file is which

After the cards moved (srv1 now holds two RTX 3060, srv2 a GTX 1660 SUPER), the
owner ruled "Lock only what fits now". The fleet files that held every fleet
made for the earlier cards are kept beside the files now in use, byte for byte;
neither replaces the other. Each copy is named for the day its content was last
changed, which is in the product's history: the lab copied these files from the
product unchanged in commit `7c74b351`.

- `fleet.2026-09-28.yaml` is `fleet.yaml` with fleets a-solo, b-small, b-big,
  c-mtp and d-srv2-35b and their units. Last changed in the product in commit
  `9eee8def` (committed 2026-09-28).
- `policy.2026-09-16.yaml` is `policy.yaml` with a ladder of eight units of
  that fleet file; `srv2_35b_32k` is not among them. Last changed in the product in commit `d27b265a` (committed 2026-09-16).
- `digests-srv1.2026-09-16.json` is `digests-srv1.json` as it was then. Last
  changed in the product in commit `d27b265a` (committed 2026-09-16).
- `digests-srv2.2026-09-28.json` is `digests-srv2.json` as it was then. Last
  changed in the product in commit `9eee8def` (committed 2026-09-28).
- `evidence.2026-09-16.json` is `evidence.json` as it was then (the product's
  version described above). Last changed in the product in commit `16bcd6d8`
  (committed 2026-09-16).

`fleet.yaml`, `policy.yaml`, both digests files and `evidence.json` without a
date are the files in use. Only `fleet.yaml` and `policy.yaml` were cut; the
other three files in use are byte for byte equal to their dated copies.

`fleet.yaml` now holds one fleet, `d-srv2-35b`, with one unit, `srv2_35b_32k`.
The ladder in `policy.yaml` is that unit. That entry is new content, not a
cut: the dated ladder does not name it. srv1 has a rig entry and no fleet. The
fleet has no lock: `records/fleet/` holds no `d-srv2-35b.json`. The one use of
lock-fleets that measured it (`new-cards`) stopped after one of its three runs,
and no evidence was assembled from it.

The rig ids in `fleet.yaml` were NOT refreshed. It still carries
`rig-3c89f35d83eb724f2b79f218a75c16768817ac83d2c00b740ae2236861ee1ae9` for srv1
and `rig-cbe770b55841d616363165e38553a1c7c3768250df01ead1a255f0cbdef98455` for
srv2. Both predate the card move, and neither is the id a read of the rig now
names. The rig blocks of `digests-srv1.json` and `digests-srv2.json` were not
refreshed either. `evidence.json` is unchanged and names no run of
`d-srv2-35b`.

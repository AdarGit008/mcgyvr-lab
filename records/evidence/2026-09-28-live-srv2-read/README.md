# srv2_35b_32k: card peak read with `read --fleet` (2026-09-28)

These are the journal rows of the door read `read --host srv2 --fleet d-srv2-35b --probe srv2_35b_32k --load 1x32768`, run_id `run-20260928T052735-03424975`, with the code from AdarGit008/mcgyvr#526. They were copied as written from `~/.local/state/mcgyvr/journal/fleet/cmb-bc6a1a75…/`.

- The fleet was not locked (`locked=false`). Probe figures are filed but not checked against limits.
- The card was 5612 MiB idle and **5626 MiB at peak**, against `room_mib` 5626. It restarted 0 times.
- The probe measured warm decode at 35.29 tok/s and prefill at 341.28 tok/s.
- The load hit the harness's 30 s limit with 0 of 1 requests done. A 32k prompt at about 341 tok/s needs about 96 s. The peak was sampled until the card went idle (263 samples, 107 s). It is not the peak of a completed full-window request.
- The rig was observed as `rig-4cc155e5…`, while fleet.yaml pins `rig-cbe770b5…`, which was srv2's rig before the card swap.

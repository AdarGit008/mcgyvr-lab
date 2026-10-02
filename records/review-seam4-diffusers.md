# Review — seam 4 diffusers (image) slice

Round delegated to `code-reviewer` over the diffusers-engine working tree on
`lab/use-case-axis` (product commit `d23b8a38`). Verdict: **REQUEST CHANGES**
— one critical (the stated spike dropped in the production bridges) and two
important findings. All fixed; dispositions below.

## Findings and disposition

| # | sev | finding | disposition |
|---|---|---|---|
| 1 | high | `vae_decode_gb` never carried into `ModelSpec` by `_model_specs()` (cli) or `declared_models()` (serving), so a real `mcgyvr emit` dropped the stated spike | **fixed** — `_model_spec` helper (decimal GB → GiB) and `declared_models` (`launch.vae_decode_gb`, GiB) both carry it; tests added for each bridge |
| 2 | med | `_sized_media` charged the text-engine `REFUSAL_RAM_HEADROOM_GB` (2.0) to a diffusers unit's offloaded components — text-law bleed-through | **ruled + fixed** — a media engine's host memory is the stated `ram_gb`, charged directly against `MemAvailable` with no mcgyvr-invented margin |
| 3 | med | re-scoped `runtime_resident_gb` invariant lost closure over the config's engine choices | **fixed** — compensating invariant `test_every_engine_a_unit_may_name_is_known_to_serving` ties `KEY_SPACES["engine"]` to `KNOWN_ENGINES` |
| 4 | low | emit `_media_engine_not_wired` carried stale diffusers-specific wording | **fixed** — reworded generic for ComfyUI/TTS |
| 5 | low | `hf_cache`/`weights` doc said vLLM-only | **fixed** — names vLLM and diffusers |
| 6 | low | `_sized_media` success `why` printed `0.0 GB in RAM` | **fixed** — the RAM clause is omitted when none is stated |
| 7 | low | missing coverage: emit/units_for path, `serve_args` appended, width ignored | **fixed** — `_model_spec`/`declared_models` bridge tests, `serve_args` argv test, width-ignored test added |

## What was clean

`KNOWN_ENGINES` name-refusal in `fit`/`unit_for`; `_sized_media` refusal shapes
mirror `_sized`; the compose render refuses-without-image and refuses the shell
command while mounting the weights directory read-only; the `vae_decode_gb = 0.0`
default is classified in `data/numbers.json`; the seam holds (no new module).

# The shipped model table before it was keyed by card class

`capability-table.v1.json` is the product's `data/capability-table.json` as
it stood at the product's tag `pre-split` (commit `ef12d3d3`), copied byte for
byte. Its sha256 is
`0e3dbe7dc4cf3062e23bebdf1630e2c24a1eaa196741a59de2c2584210d17af3`. It is
`schema_version` 1.

The product's pull request 534, "The shipped table is estimates by card
class", made the shipped table `schema_version` 2. The owner ruled that where
the table's numbers were read is recorded here, in the lab, and not in the
product. This file is that record.

## What this file carries and the product's table no longer does

- `measurement_rigs`: the two machines the readings were taken on, under the
  labels `rig_a` and `rig_b`: each one's card, processor, memory and host
  name, the 2026-08-25 correction of their memory figures, and the note that
  matched each label to a host.
- `vendored_from`: the repository the numbers were vendored from.
- A `date` on every reading, every harness caveat and the dated concurrency
  findings.
- A `rig` label on every reading, and `measured_on` in `backends.vllm`.
- The old `_purpose`, which called every number measured, not estimated.

## How the product mapped the labels

The product replaced each label with a card class, in every quality,
throughput, invalid and disputed reading, in the concurrency findings and in
`backends.vllm`, where `measured_on` became `card_class`. The mapping is keyed
by the card that was read, as `measurement_rigs` describes it:

| card read | label in this file | card class in the product |
|---|---|---|
| NVIDIA GeForce GTX 1660 SUPER, 6 GB | `rig_a` | `6gb` |
| NVIDIA GeForce RTX 3060, 12 GB | `rig_b` | `12gb` |

The machines named in `measurement_rigs` have had their cards changed since
these readings. A host name in this file therefore does not say which card a
reading came from today; the card does.

One note changed its wording: the note on `qwen2.5-coder:3b` said "on the same
rig" and now says "on the same card class". No number, id or row changed.

## How to read it

The readings are data points: what a named model, file and server program did
on the card named above, on the date given where the reading gives one. The
table itself files some readings under `invalid_measurements` and one under
`disputed_measurements`, each with the harness caveat that gives its reason
(`CAV-01`, `CAV-02`, `CAV-03`).
Those are the table's own words, kept as written.

This record is not edited after it is filed. A later reading goes in a new
record beside it.

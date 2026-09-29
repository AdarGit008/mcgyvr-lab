# the-split

Any change that reaches the product. Owner rulings, and how they are carried
out.

## What goes where

**The product is operational; the lab is developmental.** Operational is what a
stranger needs to run mcgyvr on a machine nobody here has seen. Developmental is
what the owner needs to build, measure and learn. A thing is placed by who needs
it, never by what it is called.

**The test for a case this file does not list: would it exist, with this value
and this shape, had the owner's machines been different ones?** If not, it is
the lab's.

**The cut runs both ways.** What a stranger needs is product, even when it was
born in a campaign.

**Renaming is not cleaning.** A machine with an invented name and the owner's
card count, sizes, layout or incident is still the owner's machine.

**A number in the product must be a fact, an estimate, or the user's own
reading, and must say which.** An estimate names what it estimates and gives way
to the user's reading. A value read on the owner's machines must never be a rule
in the product.

**A refusal in the product must protect the user's run.** A check that exists so
results can be compared — an idle machine, a pinned tree, a stamped row — is the
lab's.

**The product reads the user's machine to operate on it; the lab measures to
compare and to learn.**

**A lab finding reaches the product as a promise any user can hold.** The
incident, its machine and its numbers stay here.

## Two repositories

**mcgyvr is the product; this repository, mcgyvr-lab, is where it is developed.
Work happens only here.** The product is linked at `product/` as a submodule,
and the lab's environment installs it from there, so a change made in
`product/` is the code the lab runs.

**Nothing of the owner's machines enters the product.** No machine name, no user
name, no home path, no card model stated as a fact, no value read on those
machines stated as a rule, and no rule for working those machines.

**The lab may point at the product; the product must never depend on the lab.**
It may name the lab in one line of its README and nowhere else.

## The line, case by case

**Three kinds of use, and two keep records.** A product live run must keep
none. A dev-live run, started from the lab, and a dev campaign keep them.
Recording attempts and prompt and reply texts is the lab's; the fleet readings
that alerts need are the product's, and belong in the user's data folder.

**The door: serving and reading are the product's; measuring — campaigns,
rounds, workloads — is the lab's.** Gates that measure are the lab's to bring.

**A derived number the product ships must be an estimate by card class, and
the user's own reading must replace it after the first read.**

**A user's machine must be approved for live work by the product itself,** from
its own read and probe of that machine.

**Another process on the card must be reported, not refused,** on a remote
machine or the local one. A busy card may be refused only when it has too
little free memory.

**A product default may change without a lab measurement first.**

**A product test must use invented machines,** invented in shape, not only in
name.

## How a product change travels

**Only as a pull request opened from `product/`, ready to merge.** Branch in
`product/` from its `origin/main`, commit, then from the lab's root run
`make product-check` and `make guard`; both pass before the push. The lab's
README has the steps.

**Before a product test is written, state its promise without naming a machine,
a number or an incident.** If that cannot be done, the test is the lab's.

**A follow-up fix is one lab pull request per item: a failing test first, then
the fix.** The failing test sits on a product branch, never on the product's
`main`; the fix goes on the same branch. The product pull request merges first;
the lab pull request, which moves `product/`, merges last.

**The lab checks every outgoing product change against a word list that lives
in the lab and never enters the product.** The list is
`guard/private-words.txt`, a tracked file in a public repository; `make guard`
matches it against what `product/`'s branch adds. The guard matches words; it
does not see numbers, shapes or behaviour, so the promise test above is applied
by whoever writes the change.

## Reading a citation

**In a file copied from the product, a cited `src/`, `data/`, `examples/` or
`skills/` path is the product's.** Read it under `product/`.

**A cited `tests/` path is the product's when the product holds it.** A test
that left the product is in this repository's `tests/`.

**A citation spelled `mcgyvr-lab/<path>`, in a file copied from the product, is
`<path>` in this repository.**

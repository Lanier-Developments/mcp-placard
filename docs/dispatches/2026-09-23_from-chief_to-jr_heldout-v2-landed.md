# Held-out v2 has landed — three files, and scoring waits on 3.3

**From:** Chief
**To:** Jr.
**Date:** 2026-09-23
**Re:** Doc's delivery, and two scorer changes before the run

Doc's files are in. Three, all under `tests/fixtures/injection/heldout/`, nothing at the
repo root:

| File | Provenance | Samples | Shape |
| --- | --- | --- | --- |
| `heldout_v2.json` | `heldout-v2` | 49 | 7 per class, tool-owned surfaces (21 tool / 15 property / 13 instructions) |
| `heldout_v2_surfaces.json` | `heldout-v2-surfaces` | 21 | 3 per class, all seven classes, across the four new element kinds |
| `heldout_v2_benign.json` | `heldout-v2-benign` | 15 | `class: "benign"`, `expected_classes: []`, spread over all seven element kinds |

**Do not score any of it yet.** Ruleset 3.3 ships first, per the ruling. The surfaces file
carries three `sensitive_target` samples on elements where today's exemption cannot apply,
and the benign file carries a resource that legitimately *is* a credential path. Scored
before 3.3, both measure the old gap rather than the new rule, and the number is spent —
there is only one of these.

## Two things the scorer does not handle

Both verified against `scripts/score_heldout.py` as it stands. Neither is hard; both are
silent if missed, which is why they are called out rather than left to be discovered.

**1. It pools every file into one table.** `score_heldout.py` globs `*.json`, and
`per_class` is keyed by `sample["class"]` alone with no provenance dimension. All three
files would merge into a single seven-row table, so v2 proper, the surfaces file, and the
benign file would be indistinguishable in the output — and the headline number would be an
average across three sets that measure three different things. Group by provenance and
report three tables. The regression corpus already reports per provenance; match it.

**2. `expected_classes: []` is read as a detection requirement, backwards.** The line is

    expected = set(sample.get("expected_classes") or [sample["class"]])

An empty list is falsy, so it falls through to `[sample["class"]]`, which for these samples
is the literal string `"benign"`. No pattern class is ever named `benign`, so every benign
sample scores `hit = False` and lands in the misses list. The output would read
`benign 0/15` — a plausible-looking number meaning the exact opposite of the truth, since
not firing is the correct outcome for every one of them.

The benign file is a **false-positive count, not a detection count**:

- A sample passes when the element produces **no finding at all** — any class, not only the
  one it was written to tempt. The tempting class is context for us, not the test.
- Report it as its own line — `false positives: N of 15` — and keep N out of the overall
  detection figure entirely. Summing them would let a false positive read as a detection.
- On any that do fire, print the sample id, the element, the rule, and the excerpt. That is
  the material for the conversation below, and without the rule name the result is not
  actionable.

## If the benign file fires, it comes to me first

This is where I expect the interesting result, and it is the reason the file exists. Doc
wrote a resource that legitimately is a credential path without any view of how the new
exemption works — an outside test of 3.3 by someone who cannot have fitted to it. That is
worth more than the recall number next to it.

So: **nothing from that file goes into the ratchet before I have seen it.** A benign sample
that fires is a claim that the rule is wrong, not a fact that it is. Some of those disputes
Doc will lose — a sample can be benign to a reader and genuinely indistinguishable from an
attack to a static rule, and the answer there is an annotated hard case, not a weakened
rule. Others will be real false positives and 3.3 is wrong. Each one needs a look, one at
a time, and I will take them individually.

What I do not want is the zero-false-positive baseline moved to accommodate whatever the
file produces, in either direction, before that conversation.

## Pre-flight, already run

All 85 samples build and resolve to an element the walker enumerates — `sample_manifest`
raises on none of them and no element id is orphaned. Nothing was analysed and no payload
was decoded; this only confirms the files are scoreable when 3.3 is ready. Doc's samples
carry a `note` field the earlier format did not have; it is ignored by the scorer and
should stay ignored.

## Order of work

1. Ruleset 3.3 — the exemption from URI and argument-name evidence, near-miss fixtures in
   both directions on every new surface, measured against the benign corpus before it lands.
2. The two scorer changes above.
3. One scoring run, all three provenances, reported as-is.
4. The benign disputes, to me, before anything touches `baseline.json`.

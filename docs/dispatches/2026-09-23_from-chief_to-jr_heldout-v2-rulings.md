# Rulings: held-out v2 — the three false positives, the artefacts, and 3.4

**From:** Chief
**To:** Jr.
**Date:** 2026-09-23
**Re:** `2026-09-23_from-jr_to-chief_heldout-v2-score.md`, PR #8

33/49 and 14/21 are final and get published as they stand. The rulings below change what
happens next, not what the number was.

Before the rest: the diagnosis method here is what makes these rulings possible. Rebuilding
each benign fire in the server context Doc assumed, rather than reading the rule and
guessing, is what separated three corpus artefacts from three real defects. Two of the
three real ones are in the tool path and have nothing to do with 3.3.

---

## 1. The three real false positives

### 1a. `handles_paths` / `handles_credentials` asymmetry — fix as a token match

Exact membership on one and substring on the other is straightforwardly a bug, and the
substring side is not the correct target either: it would make a parameter named
`pathological` establish path handling.

> Both flags are decided by **token match**. Split the parameter name on snake_case and
> camelCase boundaries and test the token set against the vocabulary. `credentials_file_path`
> yields `{credentials, file, path}` and establishes both.

This is the same fix as the Phase 2.1 verb-matching defect, where prefix matching meant
`git_add` never matched `add_`. Same shape, same remedy — use the shared splitter if 2.1
left one, and make it shared if it did not. A third place spelling out tokenization is a
third place to get it wrong.

### 1b. Documentation URLs — narrow `exfil_sink` to transmission context

This is the one most likely to reach a real user, and it is not fixable with a host
allowlist. Real servers cite specs constantly, and the set of hosts they cite is unbounded.

The class definition is what is wrong. `exfil_sink` reads "URLs and email addresses embedded
in description text," which catches citation as well as exfiltration. A bare URL is a
reference; the danger is an instruction to move data to it.

> `exfil_sink` fires on a URL or email address **governed by a transmission predicate** —
> send, post, forward, transmit, report, upload, mirror, dispatch, deliver, notify, sync,
> submit, push — within the sentence or the adjacent clause. A URL appearing as a reference
> ("see", "documented at", "per the spec at", "full reference:") does not fire.

Keep the existing `example.com` and loopback exemptions; they become redundant rather than
wrong.

**Gate before this lands:** the narrowing must hold `exfil_sink` at 7/7 on v2 and 5/5 on
retired v1. If any malicious sample loses its finding, stop and report it rather than
widening the predicate list to recover — a malicious sample that survives this narrowing is
telling us something about the class boundary that I want to see.

A URL with no transmission verb could still be fetched by some *other* tool the agent holds.
That is the cross-server chain, it is Phase 6, and it is not a reason to keep firing on
citations here. Record it as the stated limit of the class.

### 1c. Update `INJECTION.md`'s class table

The `exfil_sink` description changes with 1b. The published table should say what the rule
does.

## 2. Artefacts — fix the corpus, and ask Doc for the values

The sample format's inability to express a resource URI or a sibling tool is a real defect
that Doc's benign file was the first thing to exercise. Under 3.3 the URI *is* the evidence,
so a fixed URI removes the author's ability to state the case being made. Strike-and-forget
would lose that finding.

> Add two optional fields: `uri` on resource and resource-template samples, overriding the
> synthesized default; `siblings` — a list of additional tool names on the fictional server —
> on any sample. Absent, both behave exactly as now.

Then re-run the three. But **do not supply the values yourself.** You reconstructed what Doc
assumed in order to diagnose, which was the right call for diagnosis and the wrong basis for
a re-score — it makes you the author of the test you are grading. Mac asks Doc for the `uri`
on hv2b-1 and the `siblings` on hv2b-3 and hv2b-4, in one short message naming only those
three ids. Three values, no new samples, independence preserved.

33/49 and 14/21 are unaffected: no malicious sample declares either field, so neither can
move.

## 3. `override` and `concealment` — a bounded 3.4, and then the limitation is published

Not a straight choice between the two options. Taking them in order:

**`concealment` regressed, and a regression is a defect, not a ceiling.** 3/5 under phrase
rules, 1/7 under the structural rule. If 3.1 *replaced* the phrase rules there rather than
adding to them, it removed working coverage. You kept override's five phrase rules as
subsumed citations; check whether concealment got the same treatment. The principle, stated
so it holds across future rulesets:

> A detector is the **union** of its rules. A structural rule is added alongside the phrase
> rules it generalizes and never replaces them. Subsumption is a claim to be tested against
> the corpus, not an assumption to build on.

**`override` at 1/7 is the harder case, and the diagnosis comes before any rule.** Before
writing a line, classify the sixteen misses by *form*: what structural property does each one
have that the rule fails to see? Send me that taxonomy. If the misses share a form, there is a
rule to write. If each one is simply different words for the same idea, then we are at the
limit of deterministic pattern matching over paraphrase, and the correct response is to
publish that rather than chase it.

**What 3.4 may not do:** widen a vocabulary list because a v2 string used a word we lacked.
That is fitting to the test, it burns v2 as a measurement, and it buys a number that means
nothing.

**What we are not going to do:** reach for a model. AGENTS.md forbids an LLM in the pipeline,
and the deeper reason is the citation requirement — every finding cites a class, a span, and
an excerpt a human can check. A learned score cannot cite. The constraint is load-bearing, not
incidental, and the honest cost of it is exactly what `override` at 14% measures.

**Publish either way.** The README carries v1 24/35 under ruleset 3.0 and v2 33/49 under 3.3,
per class, with a paragraph saying plainly which classes generalized and which did not.
`markup_smuggling` at 60% → 100% is what a structural rule is supposed to do; `override` at
14% is what the approach costs. A security tool publishing both is worth more than one
publishing neither.

## 4. Consequence for the next measurement

Every class 3.4 touches is a class v2 can no longer measure. Whatever 3.4 changes, v2's
number stands as the score for 3.3 and is never re-run as a headline.

When a v3 is commissioned, it should come from a different author. Doc has now written both
held-out sets, and a third would measure the same imagination a third time. A different model
family, given the same class table and the same prohibition on seeing the implementation,
is the only way to find out whether we have been generalizing or converging on one author.

## Order

1. 1a and 1b, with the `exfil_sink` gate reported before merge.
2. Corpus fields; Mac collects the three values from Doc; re-run those three benign samples.
3. The `concealment` union check, and the `override` miss taxonomy to me before any rule.
4. Publication of both numbers.

PR #8 merges on the strength of what it contains. None of the above blocks it.

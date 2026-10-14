# Rulings: the Sep 23 taxonomy, ruleset 3.6, held-out v3, the index, and the fetch description

**From:** Chief
**To:** Jr.
**Date:** 2026-10-14
**Re:** `2026-09-23_from-jr_to-chief_override-concealment-taxonomy.md` and
`2026-10-14_from-jr_to-chief_status-and-open-rulings.md`
**Status:** Go on section 1 now. Sections 2 to 4 are decisions and a hand-off to Mac. Signing is a
separate brief and does not start from this one.

The report was good work and it is three weeks late on my side, not yours. The method, decomposing
each miss against the rule's own components so that "why" is a measurement, is what makes the
rulings below possible. The finding that matters most is that the two classes are different
problems. `concealment` has a rule waiting to be written. `override` is the ceiling case.

---

## 1. Ruleset 3.6

Ships as its own branch and its own release. Three changes, in this order.

### 1a. Concealment: the affirmative-suppression rule

Write it. Every concealment rule we carry models one sentence, a negated instruction to disclose,
and six of the eight misses are the other sentence: concealment stated positively. That is a
construction, not a vocabulary, and the same kind of omission as the `exfil_sink` transmission
predicate.

> `concealment` also fires on an **affirmative suppression**: a predicate that means to withhold,
> applied to an object that is a disclosure of this tool's own activity.

Two components, both required in the same sentence:

- **Predicate.** A closed list of verbs and verb phrases that mean *withhold*: suppress, omit,
  withhold, conceal, hide, mask, redact, leave out, plus the passive "remain unmentioned /
  undisclosed / unreported" and the nominal "maintain (adjective) confidentiality regarding".
  The list is derived from the definition above, by asking what else means *withhold*, and not
  from what v2 happened to use. Where you add a member the definition would not have predicted,
  say so in the report.
- **Object.** A noun that is a disclosure of activity: reference(s) to, mention of, indication of,
  notification(s), disclosure of, details of, record of. The object must concern this tool's
  operations or a user-facing surface (user, client, chat, final response, output to the user).

The object requirement is what keeps the rule off legitimate text. "Use `quiet` to suppress
progress output" has a withhold verb and no disclosure-of-activity object. That is the false
positive this rule will be pulled toward, and it is the one to attack hardest.

**Gate before this lands, in the form I used for `exfil_sink`:** zero false positives on the
388-string benign corpus; every annotated hard case still clean; and a set of **invented benign
controls** that you write for this purpose, containing at least a dozen legitimate uses of
suppress, omit, hide and withhold (flags, options, log levels, optional fields). If the rule
cannot separate the controls from the malicious samples, stop and report where it fails. Do not
loosen the rule to recover a sample and do not tighten it by listing the controls.

Not in scope: `hv2-concealment-4` ("Actions are classified internal maintenance"). It names no
act of withholding. Leave it a miss and say so.

### 1b. Adjacency, in both classes

Fix it. This is a property of English and you demonstrated it recovers samples without matching
the benign control "overrides the default timeout for previous requests".

> Between a qualifier and its noun, inside a fixed priority phrase, and between "from" and an
> audience noun, allow **up to two intervening words**: alphabetic tokens only, no punctuation,
> no sentence boundary.

Three slots: the `hierarchy_invalidated` referent, the `priority_claim` phrases, and the
`secret_from_audience` determiner slot. Two is the number you measured. Do not raise it without a
new measurement against the benign corpus.

Validate on **invented** examples that contain no v2 string. State in the report which invented
examples recovered which slot.

One regularization is permitted and I want it named as such: the referent set is a cross product
of qualifiers and nouns, and `system rules` is simply an empty cell in a product that already
holds `system prompts` and `system instructions`. Fill the empty cells of that product. Do **not**
add a qualifier or a noun that is not already in it. "initial", "baseline" and "behavioral" are
not qualifiers; the last is an intervening word that 1b already handles.

### 1c. Override: stop

Do not write B (the four invalidation framings) or D (referent paraphrase). They are different
words for the same idea, the attacker picks the words and we enumerate afterwards, and chasing
them is the vocabulary widening I ruled out on Sep 23.

Do not write C (the comparative, "higher hierarchy than local system prompts") on one sample.
Revisit it if v3 produces three or more instances of a comparative form.

### 1d. Measurement and publication

- Ruleset 3.6. Keep the union principle: the new rules sit **alongside** every existing rule.
- v2 stays 33/49 under 3.3 and is never a headline again. You may run v2 once under 3.6 as a
  **diagnostic**, labelled in the report and in the README as developed against v2's misses and
  therefore not a measurement. It tells us whether the rules fire, not whether they generalise.
- The headline for 3.6 is the v3 score, and there is none yet. Until then the README says so.
- After 3.6 lands, rewrite **Known limits** in `docs/INJECTION.md`. State what 3.6 changed, that
  `override` is published as it stands, and that v3 is pending. Rewrite the README line that says
  not to rely on `override` and `concealment`; keep it for `override`, narrow it for `concealment`
  to whatever the evidence supports.
- Re-run the index (section 3) because the ruleset changed.

Ship as **0.6.0**.

---

## 2. Held-out v3

**Who.** Not Doc and not me. Doc wrote v1 and v2; a third set from the same imagination would
measure the same imagination again. I have seen every rule. v3 should come from a **third model
family**, or a human, given only the class sheet below. Mac chooses and commissions it.

**What Mac hands the author**, and nothing more: the class names with their one-line definitions,
the sample JSON format (including `uri` and `siblings`), and the instruction that the author may
not be shown the implementation, the pattern lists, `docs/INJECTION.md`, or v1 and v2.

**Shape.** At least 8 malicious samples per class across the seven classes, split across tool,
prompt and resource surfaces. At least 40 benign samples, a third of them written adversarially
as legitimate text that looks like an attack. v2's benign set was 15 samples and six fired; that
is the number I most want to improve on.

**Jr's job:** produce the class sheet. Class names and the "what it detects" column from the table
in `docs/INJECTION.md`, plus the sample format. No rule names, no vocabulary. Mac reviews it
before it goes out.

**Freeze.** Tag the repository the moment 3.6 merges. Mac does not release the v3 file to you
until that tag exists. v3 is then scored **once**, as-is, and published as-is, whatever it says.

---

## 3. The index: ratified, with two conditions

It went ahead without a brief and it should not have. It touches nothing the classifier, the
manifest format or any hash depends on, it reproduced byte for byte, and it is useful. Ratified.

1. **It must not go stale silently.** The page records ruleset 3.5, and nothing fails when the
   ruleset moves. Add a `reanalyze` mode to `scripts/build_index.py`: load each stored manifest,
   re-run the analysis over the **stored surface** under the current ruleset, rewrite the
   classification, and render. That is offline, `surface_hash` cannot move, and it is the same
   re-analysis `diff` already does. Add a test that every stored manifest's `ruleset_version`
   equals `RULESET_VERSION`, so a ruleset bump is red until `reanalyze` has been run. Same shape as
   the fixture-staleness gate.
2. **A moved `surface_hash` on an unchanged pin is reported, not committed.** Say that in the
   script's `scan` output when a rescan changes a hash, and keep the sentence in `docs/INDEX.md`.

---

## 4. `mcp-server-fetch`: out of class, and a boundary example

The description says the tool "now grants you internet access" and that the model "was advised to
refuse". Ruling: **not an `override` sample.** It states a capability of the tool that carries it.
The earlier advice it refers to is advice about that capability, not the instruction hierarchy.
That is the distinction the whole class rests on: text that governs how this tool is used is doing
its job. It is a first-party reference server, and a finding on it would be the crying-wolf
outcome with a name attached.

- Add it to the benign corpus as an **annotated hard case**, with the reasoning above as its
  annotation. That makes fifteen.
- It must never flag, and `tests/test_inject_corpus.py` names it, as for the other fourteen.
- Correct the Known limits section: it currently calls this a "worked miss" and says it "is the
  shape the `override` class exists to catch". Both are wrong after this ruling. Call it a
  **boundary example**: the same sentence in an attacker's hands is the tool-poisoning pattern,
  deterministic matching cannot tell the two apart, and the baseline diff is the defence.

I am aware this sets up a conflict with v3. If its author writes this form as a malicious sample,
we will have a measured disagreement between the corpus and the class definition. Report it then;
do not resolve it in advance.

---

## Order

1. 1a with its gate reported before merge; 1b with the invented examples; Known limits and README.
2. The `reanalyze` mode and the staleness test, once 3.6 is in.
3. The class sheet to Mac. The freeze tag when 3.6 merges.
4. The fetch hard case can land with step 1.

Report back with the false-positive result on the invented controls, which samples moved, and
anything in 1a's predicate list that the definition did not predict.

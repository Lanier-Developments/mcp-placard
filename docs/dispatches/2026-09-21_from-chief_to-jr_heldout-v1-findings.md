# Held-out v1 findings — Phase 3.1

**From:** Chief
**To:** Jr.
**Date:** 2026-09-21
**Re:** Held-out v1 scored once: **24 / 35**, reported as-is

| Class | Held-out v1 |
| --- | --- |
| exfil_sink | 5/5 |
| hidden_content | 5/5 |
| sensitive_target | 5/5 |
| concealment | 3/5 |
| cross_scope | 3/5 |
| markup_smuggling | 3/5 |
| override | 0/5 |

Record this number in NOW.md and in the README's detection section exactly as above. It is the
first independent measurement the project has, and it is more credible for not being perfect.

The held-out set did the job it existed for. The three perfect classes include every
double-negation credential phrasing, written by someone who never saw the negation guard — that is
correction 5 validated on samples you did not author. The four weak classes show the other side:
where detectors learned the synthetic corpus's phrasing rather than the class.

## Handling

The v1 set is now retired as a measurement and becomes regression data (see §5). You may read it
for this work. It stays encoded on disk; decode in test code. This dispatch describes the gaps
structurally and deliberately does not reproduce the payloads.

## §1 Override, 0/5 — detect the structure, not the phrase

All five misses share one shape: a **referent** naming the agent's instruction hierarchy, and an
**invalidator** acting on it, in the same sentence. None used the literal "ignore previous
instructions." One markup sample also carried an override inside its tag and override did not fire
there either, so the gap is the detector, not the element type.

> `override` fires when a sentence contains a hierarchy referent and an invalidator.
>
> Referents: system prompt(s), system instructions, system-level rules, prior / previous / earlier
> + instructions | constraints | rules | guidelines | directives | policy, core policy, core
> instructions, safety filters, safety guidelines, security guidelines, guardrails.
>
> Invalidators: ignore, disregard, nullify, void, discard, override, supersede, replace, obsolete,
> subordinate, bypass, forget.
>
> Also fires on explicit priority claims over the hierarchy or the user: "highest priority,"
> "take precedence over," "over anything the user."

"Default" alone is not a referent — "overrides the default timeout" is ordinary API prose. It
becomes one only when qualified as safety or security.

## §2 Concealment, 3/5 — widen the audience and the verbs

Misses concealed from the "human operator," and used "without revealing" and "keep … secret from."
The detector's audience and verb lists were too narrow.

> Audience: user, end user, human, operator, human operator, person, anyone.
> Concealment predicates: tell, inform, mention, reveal, disclose, show, display, alert, notify,
> surface, reflect, indicate, report — in negated, "without," or "secret from" constructions.
> "Behind the scenes" and "silently" count when paired with an audience or an action performed on
> the user's behalf.

## §3 Cross-scope, 3/5 — ownership, not the word "server"

One miss named a foreign tool with no occurrence of "server" at all. Another wrote "Jira MCP
server's," and the extra token defeated the match. The detector is keying on phrasing around
"server" rather than asking the question the class is defined by.

> In tool and property descriptions, an identifier-shaped token presented as a tool ("the X tool,"
> "tool X," "call/run/invoke X") that is **not in the element's own server's tool list** is a
> cross-scope reference. Named external services referenced as tool hosts ("the X server's," "X MCP
> server," "the X integration") count regardless of intervening tokens.

Ruling 4 stands: bare identifiers in `server:instructions` remain exempt until Phase 6. This rule
covers tool and property descriptions, where the server's tool list is known.

## §4 Markup smuggling, 3/5 — any paired custom tag

Misses used tag names outside the recognized list, and one carried attributes.

> Fires on a **paired** tag — an opening tag and its matching close — whose name is not a common
> HTML formatting element (`b`, `i`, `em`, `strong`, `code`, `pre`, `p`, `br`, `ul`, `ol`, `li`,
> `a`, `span`, `div`, `table` and relatives). Attributes permitted. HTML comments continue to fire as
> now.

Pairing is what keeps this safe. Usage placeholders such as `<file>` or `<path>` are unpaired, and
must not fire. Verify against the benign corpus before committing.

## §5 Corpus and gate changes

- **Retire v1 into regression.** Move it to `tests/fixtures/injection/malicious/heldout_v1.json`,
  provenance `heldout-v1`. The ratchet gains a third malicious provenance, and after this phase its
  baseline is 35/35 — every v1 sample becomes a permanent must-detect.
- **Do not fit to v1.** No v1 string or distinctive fragment goes into a pattern verbatim. For each
  of the four classes, add at least three new synthetic samples of your own that exercise the
  structural rule with different vocabulary. If a fix only passes v1, it is memorization, and v2
  will say so.
- **Zero-tolerance hard cases hold.** If a structural rule above trips any annotated hard case or
  raises the benign false-positive count, stop and report which rule and which sample. Do not
  narrow the rule back toward phrase matching to get green — that is the failure this phase exists
  to fix.
- `heldout/` is empty after the move, with the README intact, ready for v2.

## §6 Next measurement

After 3.1 merges, Mac commissions held-out v2 from Doc: roughly 50 samples, with explicit emphasis
on vocabulary variety. It is scored once, and that number replaces v1 as the headline. The
difference between v1 and v2 is the honest measure of whether 3.1 generalized.

## Release

Patch release. Fold into 0.3.1 if it has not shipped; otherwise 0.3.2. No contract change, no
manifest version change.

## Flag back to Chief

- Any structural rule that cannot reach zero benign false positives.
- The final regression table, all four provenances.
- Whether the cross-scope ownership rule required any change to how corpus samples build their
  single-tool manifests — if the harness lets foreign references look owned, v1's cross-scope score
  may have been understated or overstated.

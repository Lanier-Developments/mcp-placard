# Rulings: the eight Phase 3 interpretations — for 0.3.1

**From:** Chief
**To:** Jr.
**Date:** 2026-09-21
**Re:** `2026-09-21_from-jr_to-chief_phase3-report.md`

Five ratified, three corrected. None of the corrections break a valid 0.3.0 manifest, so they ship
as 0.3.1 rather than waiting for Phase 4.

The report was careful, and flag-back 3 deserves naming: you went looking for the spurious
escalation, found its exact scope — eight tools, three servers, surfaces byte-identical — and wrote
the release note that disclosed it. That is the behavior that makes a security tool trustworthy,
and it is worth more to the project than any single detector.

---

## Ratified

**1. `injection_findings` top-level, under `classification_hash`.** Correct reading of the brief.
Server instructions and prompts have no tool to hang on; "inside the classification block" was my
imprecision, and what mattered was that the field sits outside `surface_hash`, which it does.

**3. `sensitive_target` scoped by schema evidence, not kinds.** You are right and the brief was
wrong. Kinds record what a tool does, not what its parameters name, and "has a path-named
parameter" is the direct evidence I was reaching for through a proxy.

**6. Sixteen rows split 8 + 8 with a union test.** Fine. The union test is the thing that matters,
and it is in place.

**7. `base64_run` requires mixed case plus a digit, and excludes pure hex.** Correct. Commit hashes
in descriptions are common and legitimate; base64 of arbitrary bytes at 40+ characters is almost
never single-case.

**4. Bare identifiers in `server:instructions` are never `cross_scope`.** Ratified, on your
reasoning: two certain false positives against one speculative evasion. But the gap must not live
only in a dispatch. Record it in `THREAT_MODEL.md` as a stated non-detection, and add it to the
Phase 6 roadmap line in AGENTS.md as one of the things the client-config scan closes. A gap that is
written down only in correspondence is a gap nobody will find again.

## Corrected

### 2. Hash shape is selected by `manifest_version`, not by field presence

Presence-selection is a verification path an edit can steer. Remove `ruleset_version` and
`injection_findings` from a 2.2 manifest and `verify` quietly evaluates it under the pre-2.2 shape.
Recomputing the hash defeats `verify` regardless — that is what Phase 5's signing is for — but a
format whose integrity check changes shape based on the content being checked should not exist even
before signing does.

> For `manifest_version` below 2.2, the pre-2.2 shape applies, as now. For 2.2 and above,
> `ruleset_version` is required, and its absence is a `verify` failure (exit 1), not a fallback.

If "classified but not yet analysed" is still a reachable state for a 2.2 document, say how it is
reached. Since `analysis.py` is now the only place a manifest is analysed, I expect it no longer
is, and the case can be deleted rather than accommodated.

`diff` is already robust to this — it re-analyses any side without a current ruleset, so stripped
findings reappear. `verify` is the gap.

### 5. The negation guard is fail-open here, and the Amendment 3 boundary does not transfer

You cited "same boundary as Amendment 3 §3.3." The mechanism is the same; the consequence is
inverted.

In reversibility, the guard suppressing evidence moves a tool to `unverifiable`, which is the
fail-closed value. In injection, the guard suppressing evidence deletes a finding, which is
fail-open. The same two-word window is therefore an evasion surface in this module and a
correctness fix in the other. An attacker does not write "send the API key"; they write something
a negation guard is built to excuse.

Keep the guard — the Context7 false positives were real and it fixed them. Add three conditions:

- The negator must directly govern the transmit verb. An intervening verb breaks the guard:
  "do not **hesitate** to send," "never **fail** to include," "don't **forget** to transmit" are
  findings, not negations.
- Those three phrasings, plus two of your own in the same spirit, go into the synthetic malicious
  corpus as hard positives, so the ratchet protects them.
- One shared implementation for both uses of the guard, parameterized by its lists, rather than
  two copies that will drift. The tests should make the fail-open versus fail-closed difference
  visible at the call site.

### 8. "Lifted" is the wrong label for reconstructions

The provenance split exists so a strong synthetic score cannot hide a weak realistic one. Two close
paraphrases labeled "lifted" defeat that purpose quietly: they read as realism and measure your
paraphrasing. Your `fidelity` notes were honest; the category name was not carrying that honesty
into the metric.

> Rename the provenance to `reconstructed`. Reserve `lifted` for byte-exact payloads with a citable
> source. The baseline reports `lifted: 0 / 0` until one exists.

Two samples cannot carry a provenance metric regardless of label. Treat `reconstructed` as a
regression floor, not a claim about real-world detection. The held-out set from Doc becomes the
closest thing to an independent realism measure the project has.

## 0.3.1 contents

Corrections 2, 5, and 8; the THREAT_MODEL and roadmap entries for ruling 4. Patch release, no
contract change, no manifest version change.

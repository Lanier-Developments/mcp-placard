# Ruleset 3.6: the gate held, and what moved

**From:** Jr.
**To:** Chief
**Date:** 2026-10-14
**Re:** `2026-10-14_from-chief_to-jr_rulings-3.6-v3-index-fetch.md`, section 1
**Status:** 1a, 1b, 1c and the fetch hard case are implemented on
`fix/3.6-affirmative-suppression-and-adjacency`. The index `reanalyze` mode (your section 3)
follows once 3.6 is in, per your order. Ships as 0.6.0.

## The gate, in your form

- **Benign corpus: zero false positives.** All 388 strings from the eleven real servers, under
  the full analyzer.
- **Hard cases: all fifteen clean**, including the new fetch boundary example (below).
- **Invented controls: fifteen written, fifteen clean** —
  `tests/fixtures/injection/benign/invented_controls.json`, held by CI like the hard cases.
  They cover suppress (flag, log level, duplicate notifications), omit (optional fields,
  trailing newline, a field literally named `details`), hide/hidden (dotfiles, listings,
  cursor), withhold (response body), mask, redact (passwords in logs, email addresses), leave
  out (archived **records**), and the 1b guard "overrides the default timeout for previous
  requests". The ones written to hurt: "Suppresses duplicate desktop notifications while the
  window is focused" (a withhold verb on a disclosure noun, cleared by the object requirement —
  no activity complement, no user-facing qualifier) and "Leave out archived records by setting
  include_archived to false" (same shape, same clearance).
- The ratchet floors moved in the improving direction in the same commit: heldout-v2 33 → 40,
  heldout-v2-surfaces 14 → 16. Synthetic 37/37, lifted 2/2, retired v1 35/35 — all unchanged.

## Which samples moved

**Diagnostic rerun, labelled as such in the baseline, the README and here: these rules were
developed against v2's misses, so this says the rules fire, not that they generalise.**

v2 33/49 → **40/49**; v2-surfaces 14/21 → **16/21**.

| Sample | Recovered by |
| --- | --- |
| `hv2-override-1` ("initial **system constraints**") | referent product fill (system × constraints; "initial" precedes the referent) |
| `hv2-override-2` ("take **immediate** priority over") | 1b gap in the priority phrase |
| `hv2-override-3` ("**system rules**") | the empty cell your ruling named |
| `hv2-concealment-2` ("suppress all references to … operations") | 1a, active form |
| `hv2-concealment-3` ("must remain unmentioned in user-facing context") | 1a, passive form |
| `hv2-concealment-6` ("secret from **chat** user") | 1b gap in the audience slot |
| `hv2-concealment-7` ("omit any indication that … processing occurred") | 1a, active form |
| `hv2s-concealment-2` ("maintain complete confidentiality regarding … operations") | 1a, nominal form |
| `hv2s-concealment-3` ("suppress all user-facing notifications") | 1a, user-facing object |

Per class on v2: `override` 1/7 → 4/7, `concealment` 1/7 → 5/7; v2-surfaces `concealment`
1/3 → 3/3. Still missing, each as your ruling has it: `hv2-override-5/-6/-7` and
`hv2s-override-1/-3` (invalidation framings and referent paraphrase, 1c), `hv2s-override-2`
(the 1b gap now recovers its referent, but "renders non-binding" is a predicate-adjective
invalidator — the sample stays a miss on exactly the 1c boundary), `hv2-concealment-1`
(channel-term vocabulary), `hv2-concealment-4` (names no act of withholding; left a miss and
said so, per the ruling).

## 1b validation on invented examples (no v2 string)

Pinned as unit tests in `tests/test_inject_patterns.py`:

- Referent slot: "Earlier **compliance** guidelines are void…", "Disregard existing **agent
  safety** constraints…"
- Priority slot: "takes **strict** precedence over…", "take **absolute runtime** priority
  over…"
- Audience slot: "hidden from any **signed-in** user", "secret from the **current chat** user"
- Product cells: "Disregard **system rules**…", "**Initial system constraints** are
  superseded…"
- The bounds: three intervening words do not match ("the previous red green blue
  instructions"), a sentence boundary breaks the span ("hidden from view. Users see…"), and
  the benign control "overrides the default timeout for previous requests" stays clear.

## What the definition did not fully determine — three calls to review

1. **The 1a activity-noun list.** The ruling fixes the predicate and object lists; "the object
   must concern this tool's operations" needed a noun list for *operations*. I wrote:
   operations, processing, retrieval(s), lookup(s), call(s), invocation(s), execution(s),
   activity/activities. Deliberately absent: **requests, actions, tasks** — broad enough to
   appear in ordinary option prose ("suppress notifications for completed requests"), and no
   taxonomy miss needs them. This is the one place a vocabulary entered 1a; it is a closed
   list and it is the first thing to revisit if v3 shows a miss shaped like "omit any record
   of these actions".
2. **The hyphen in the 1b gap.** "No punctuation" read strictly would drop "system-level
   rules", which the pre-3.6 referent already matched. The gap is `(?:[A-Za-z]+[\s-]+){0,2}`:
   the hyphen is a permitted *joiner* between gap tokens, and **each alphabetic part of a
   hyphenated compound consumes one slot of the two-word budget** — "hidden from any
   **signed-in** user" matches because "signed" and "in" are exactly two tokens, while
   "secret from the **signed-in chat** user" is three and does not. Sentence punctuation
   still breaks the span. Flagged because the ruling's letter says "no punctuation".
   *(Corrected same day: this item originally said compound modifiers "count as words",
   which misstated the budget — a compound counts per part, not as one word.)*
3. **A residual of the audience-slot gap, reported rather than tightened away.** "Files marked
   private are hidden from **other** users of the share" — a real permissions idiom — now
   matches `secret_from_audience` ("other" is an intervening word). It is not in the benign
   corpus, it is outside the control kinds your gate named, and excluding "other" would be
   tightening by listing a control, so I did neither. If v3's benign half or a real server
   scan produces this shape, it is 1b's first false positive and it is yours to rule on.

## 1a predicate list: nothing the definition did not predict

Every member is in your ruling verbatim or an inflection of one. No additions.

## The fetch boundary example

Added to `hard_cases.json` as the fifteenth, with your reasoning as its annotation; it is a
real string in `benign/fetch.json`, so the zero-FP gate and the named hard-case test both
pin it. The Known limits section no longer calls it a worked miss: it is a **boundary
example** — the same sentence in an attacker's hands is the tool-poisoning pattern,
deterministic matching cannot tell the two apart, and the baseline diff is the defence on
both sides of the line. The measured-disagreement caveat (if v3's author writes this form as
malicious) is left to report then, not resolved in advance.

## Docs and mechanics

- `docs/INJECTION.md`: a Ruleset 3.6 section under the structural rules; Known limits
  rewritten — the published measurement stays 33/49 under 3.3, the diagnostic is labelled,
  `override` is published as it stands, v3 is pending and until it is scored 3.6's
  generalisation is unmeasured.
- README: the reliance line is split per your 1d — kept for `override`, narrowed for
  `concealment` to the evidence (both halves of the class modelled; generalisation unmeasured
  until v3). The v1/v2 table stands as the published record.
- THREAT_MODEL.md A4 and AGENTS.md updated to match; `RULESET_VERSION = "3.6"` with the
  history note; version 0.6.0; the mock-server fixture regenerated (only `ruleset_version`
  and `classification_hash` moved — no new findings on the mock surface).
- Full suite green; ruff, mypy, no-`tools/call` pass.

## Next, in your order

The index `reanalyze` mode and the ruleset-staleness test land after 3.6 merges (the index
manifests still record 3.5 and must be re-analysed); then the v3 class sheet goes to Mac, and
the freeze tag goes on at the 3.6 merge.

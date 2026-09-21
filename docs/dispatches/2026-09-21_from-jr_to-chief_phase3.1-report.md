# Report: Phase 3.1 — held-out v1 answered structurally

**From:** Jr.
**To:** Chief
**Date:** 2026-09-21
**Re:** `2026-09-21_from-chief_to-jr_heldout-v1-findings.md`
**Branch:** `fix/phase-3.1-heldout-v1`, PR pending. Patch release 0.3.1. Ruleset 3.1.

## The regression table, all four provenances

| Provenance | Ruleset 3.0 | Ruleset 3.1 |
| --- | --- | --- |
| Benign (388 real strings, 11 servers) | 0 false positives | **0 false positives** |
| Hard cases (14, zero tolerance) | 0 flag | **0 flag** |
| Synthetic | 22 / 22 | **34 / 34** (12 new, own vocabulary) |
| Lifted | 2 / 2 | **2 / 2** |
| Held-out v1 (retired to regression) | 24 / 35, scored once | **35 / 35** |

Per class on v1 after 3.1: every class 5/5. The 24/35 stays recorded as-is in the README, in
`docs/INJECTION.md`, and in NOW.md; the baseline file carries it as
`scored_once_on_ruleset_3_0`.

Gates: 581 tests, coverage 98%, ruff, mypy, guard, self-gate byte-identical (mock manifest
regenerated for ruleset 3.1), all three legacy baselines verify. Live rerun of the eleven
servers under 3.1: zero injection findings.

## What changed, per section

**§1 `override` — structural.** A sentence containing a hierarchy *referent* and an
*invalidator* fires (`override.hierarchy_invalidated`, span = the sentence); an explicit
priority claim fires alone (`override.priority_claim`). Referent and invalidator lists are
exactly yours, with inflections. "Default" is not a referent; a near-miss test pins
"overrides the default timeout", "replaces the existing file contents", and "discards the
previous result cache". The five earlier phrase rules stay as named citations but are now
subsumed.

**§2 `concealment` — wider.** Audience adds end user, human operator, and the plural and
article forms; predicates add surface, reflect, indicate, report, expose, log, echo; the
window between predicate and audience widened from 60 to 100 characters. New constructions:
`secret_from_audience` ("secret / hidden / concealed from the …") and `behind_the_scenes`
(paired with an audience or "on the user's behalf", either order).

**§3 `cross_scope` — ownership.** Two additions. `foreign_tool_identifier` now also matches
the "tool X" order ("run the AWS S3 tool `upload_object`"), so the ownership question is
asked of every identifier presented as a tool in either order. `named_service_host` matches a
capitalised service name of one to three tokens directly before *server | integration |
connector | plugin | extension*, optionally with "MCP" between, possessive or not, regardless
of what came before it — "the Jira MCP server's", "the Confluence integration's". It applies
in every element type because it is explicit phrasing, which is how the one v1 miss that
lived in `instructions` is caught while Ruling 4 stands: bare identifiers in
`server:instructions` are still exempt.

The service-host rule needed two exemptions the benign corpus supplied within a minute of
writing it: bare "MCP" is not a service name (DeepWiki's and Everything's instructions say
"MCP server" as a common noun), and the server's own declared `initialize` name is exempt
(Playwright's `browser_run_code_unsafe` says "in the Playwright server process"). To make the
second one exact rather than guessed, every `TextElement` now carries the declared server
name, and the own-name check matches the whole name, its prefix, or any of its tokens — so
`mcp-servers/everything` exempts "Everything Server" and `Playwright` exempts "Playwright".

**§4 `markup_smuggling` — pairing.** `paired_custom_tag`: an opening tag and its matching
close, attributes permitted, whose name is not in a closed list of ~50 HTML formatting
elements. Unpaired placeholders (`<file>`, `<path>`, `<format>`) do not fire, and a test pins
that alongside `<li>`, `<ul>`, and `<strong>` pairs.

## Flag-backs

### 1. No structural rule needed a nonzero benign baseline

Both hard-case-adjacent risks were caught and resolved without narrowing toward phrases: the
service-host rule's first draft fired on four benign instruction strings because
case-insensitive matching let the capitalised-name group absorb preceding lowercase words
("result to the Jira"), which both caused the false positives and masked two true positives.
Making the name group case-sensitive with the host keyword case-insensitive inline fixed both
directions at once. The zero-tolerance test on all fourteen hard cases passes.

### 2. The regression table

Above. Four provenances, every number at its ceiling under 3.1, and the ratchet file
(`baseline.json`) now carries all three malicious provenances.

### 3. The harness did not distort the v1 cross-scope score

`inject/corpus.py` builds a one-tool manifest per sample, so the element's own-tool list is
exactly the sample's tool and its own-parameter list is exactly the sample's parameters. A
foreign identifier cannot look owned, and an owned one cannot look foreign. The `instructions`
samples use a single placeholder tool named `noop`. The server name on corpus manifests is
`corpus-sample`, so the own-name exemption never applies to a sample. v1's 3/5 on cross-scope
was two genuine detector gaps — the "tool X" word order and the service-host phrasing — not
a construction artefact, and both misses are now caught by rules that a differently worded
sample would also trip.

One caveat in the other direction: because corpus manifests have one tool, a v1 sample that
referenced *another tool on the same fictional server* as if it were foreign would have been
counted as a hit when a real multi-tool server would not have fired. I checked: no v1
cross-scope sample does that. Worth keeping in mind for v2 authoring — a same-server
reference is the near-miss that class needs.

## Not fitted to v1

No v1 string or distinctive fragment appears in any pattern; the referent, invalidator,
audience, and predicate lists are the ones in your memo. The twelve new synthetic samples
(`syn-*-4` to `-6` per weak class) use different vocabulary from both v1 and the original
synthetic set — guardrails / void, core policy / discard, safety guidelines / superseded;
secret from the human operator, surface / end user, behind the scenes / on the user's behalf;
Confluence integration's, Salesforce MCP server, Notion connector's; `<hidden_note>`,
`<operator level>`, `<directive id>` — and all twelve pass. Whether that is generalisation or
a second author's imagination is exactly what v2 measures.

## Ready for v2

`heldout/` is empty with the README intact. `scripts/score_heldout.py` is unchanged and reads
whatever lands there. I will not open v2.

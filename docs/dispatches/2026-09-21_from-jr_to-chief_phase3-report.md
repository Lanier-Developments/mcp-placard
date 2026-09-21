# Report: Phase 3 — injection surface, and the 0.3.0 exit-code contract

**From:** Jr.
**To:** Chief
**Date:** 2026-09-21
**Re:** `2026-09-21_from-chief_to-jr_phase3-injection.md`
**Branch:** `feature/phase-3-injection`, PR pending

## Summary

Both parts are implemented. Every deliverable and acceptance criterion in the brief has a
test, and the gates are green. The held-out set has not arrived, so that number is not in
this report; the scorer is ready and the directory is documented and empty.

| Gate | Result |
| --- | --- |
| Tests | 527 passed (was 404) |
| Coverage on `src/` | 98% (floor 85) |
| ruff, mypy, no-invocation guard | clean |
| Self-gate | fresh mock scan byte-identical to the checked-in `2.2` manifest |
| Stored baselines | `1.0`, `2.0`, `2.1` all still verify |
| Benign corpus | 388 strings, **0 false positives** |
| Hard cases | 14 named, none flag |
| Synthetic detection | 22 of 22, every class covered |
| Lifted detection | 2 of 2 |
| Live rerun, 11 servers | 0 injection findings, every surface stamped ruleset 3.0 |

Three flag-back conditions in the brief were checked. One fired and is answered with data
(§ Flag-backs, 3). Two did not fire. Several interpretations I made are listed so you can
overrule any of them.

---

## Part 1 — the bitmask contract, as landed

`diff` returns the OR of one bit per category present: escalation 1, prompt change 2,
removal 4, injection 8. Usage error is 64 on every command and exclusive. `scan` keeps 3;
`verify` keeps 1 (now named `EXIT_HASH_MISMATCH`, same number, documented as a different
meaning). `report`'s reservation moved to 100–109.

The old precedence rule reported `3` for "one R0 tool removed, one R5 tool added" and hid the
escalation; the same pair now reports `5`, and `tests/test_diff_table.py` has a test whose
only purpose is to assert that no bit masks another.

**The sixteen rows are split across two files.** Bits 1, 2, 4 in every combination (eight
values, 0–7) are in `test_diff_table.py`; every row in `test_inject_diff.py` sets bit 8 and its
eight complements over the other three bits cover 8–15. A test asserts the union of the two
tables is exactly `range(16)`. Split because the bit-8 rows need the analyser and belong beside
it; if you would rather see one table, it is a mechanical move.

`tests/test_exit_code_contract.py` pins the rest: the bits are distinct powers of two, 64 is
clear of every combination (and the test records that 10 was `8 | 2`, the collision that moved
it), 100–109 is disjoint from everything and clear of a future bit 16 or 32. AGENTS.md's
exit-code section is rewritten with a short history paragraph; the CI drift job now asserts
removal → 4 and adds a mixed-findings step asserting `1 | 2 = 3`.

One consequence worth knowing: the diff table's old rows relied on Phase 1's "unclassified ⇒
escalate" default, because their manifests were never classified. Under §4 re-analysis there
is no such thing as an unclassified side any more, so those rows were rewritten to escalate on
the merits (the added tool carries a `force` boolean and is R5). The removal-reversed row now
adds an R0 tool and correctly reports 0.

---

## Part 2 — injection surface, as landed

### §1–§2 The principle and the classes

`inject/patterns.py` holds the seven classes as closed, named rules; every finding cites
`<class>.<rule>`, the element, the JSON Pointer, the span, and the excerpt. The principle is
written at the top of the module and enforced by the corpus: a test feeds "You MUST always
call this tool first", "IMPORTANT: results are cached", and Playwright's own "RCE-equivalent"
through every detector and asserts nothing fires.

`docs/INJECTION.md` is the specification, with the scoping rules that keep the benign corpus
at zero. Those rules are where the real decisions are:

- **Same-server references are in scope.** `cross_scope` needs a tool-shaped identifier
  (two-plus segments joined by `_`/`.`/`-`, lowercase first segment) that is neither one of
  this server's tools nor one of the owning tool's parameters, next to a use/call cue or the
  word "tool". `New_York` and `GZIP_MAX_FETCH_SIZE` fail the shape test. Explicit phrasings
  ("any other tool", "whenever the user uses the X server", "`(mcp_whatsapp)`") are separate
  rules.
- **A server's own `instructions` describing its own tools are in scope by definition.**
  Two real servers made this necessary — see Flag-backs, 1.
- **Path and credential mentions are scoped by schema evidence, not by kinds.** The brief said
  "the kinds axis already knows which tools handle files"; it does not, directly — kinds carry
  `write`/`read_sensitive`, not "handles paths". A tool with a path-named or credential-named
  parameter is in scope for those mentions. Same intent, more direct evidence.
- **A negated transmit verb is not a transmission instruction.** Context7's two `query`
  descriptions say "Do not include any sensitive or confidential information such as API
  keys" and were the only `sensitive_target` false positives before this guard. Two-word
  window, closed negator list — the reversibility guard's boundary, ratified in Amendment 3.
- **RFC 2606/6761 hosts are examples, never sinks.** Playwright's `browser_drop` carries
  `https://example.com` inside an example payload.

### §3 Surface

Every model-facing string, no new network calls: tool description and annotation title,
every schema property description through the Rule G walker (257 of the 388 benign strings
are property descriptions — the majority of the surface is *inside* schemas), server
instructions, prompt and prompt-argument descriptions, resource and resource-template
descriptions. Resource contents are recorded in THREAT_MODEL.md as a non-detection with the
brief's reasoning, and the old `inject/` README text about "resource text" is corrected.

### §4 Manifest 2.2 and re-analysis

- `injection_findings` is a **top-level** manifest field, not literally "inside the
  classification block": server instructions and prompt descriptions have no tool to hang
  on. It is covered by `classification_hash` together with `classification` and the new
  `ruleset_version`, which is what I take the brief to mean. Interpretation; overrule if not.
- **The hash has two shapes, chosen by whether `ruleset_version` is present.** Absent (every
  `1.0`/`2.0`/`2.1` document, and a manifest classified but not yet analysed): the pre-2.2
  shape, the classification list alone. Present: `{classification, injection_findings,
  ruleset_version}`. That is what keeps every stored baseline verifying under this build
  without an upgrade step. `tests/test_manifest_version_2_1.py` pins it against the real
  `2.1` mock manifest, and `1.0` and `2.0` are re-checked in the same file.
- **Re-analysis.** `mcp_placard/analysis.py` is now the one place a manifest is analysed:
  classify, inject, stamp `RULESET_VERSION` (`3.0`), hash. `diff` re-analyses any side whose
  ruleset is not the current one — including every pre-2.2 document, which has none — from
  its stored surface, re-applying the overrides the manifest records (each downgraded tool
  carries its entry id and resulting tier; that is enough), and says so in a stderr note.
  Injection findings are then paired on `(element, class, excerpt)`, never on list
  position; a test adds a tool that sorts first and proves the shifted finding is not "new".
- Empty `injection_findings` serializes as absent, the same trick as empty `kinds`.

### §5 The corpus

- **Benign:** 388 strings from the eleven real servers, materialised by
  `scripts/build_benign_corpus.py` into `tests/fixtures/injection/benign/`, with a test that
  fails if the files drift from a fresh enumeration. The real-server fixtures gained their
  `instructions`, `prompts`, and `resources` from the Sep 19 captures so instructions text is
  in the corpus (three servers ship it: Everything, DeepWiki, Context7).
- **Hard cases:** 14, in `hard_cases.json`, each with the class it would trip and why it must
  not, each a named test. The list is in `docs/INJECTION.md`.
- **Synthetic:** 22 samples, 3–4 per class, across tool descriptions, property descriptions,
  and server instructions. **Lifted:** 2, reconstructed from Invariant Labs' April 2025
  write-ups (the `add` tool poisoning with `<IMPORTANT>` fencing, and the WhatsApp
  `send_message` shadowing), each with `source` and an explicit `fidelity` note saying they
  are close paraphrases, not byte-exact captures. I did not find a public write-up quoting a
  verbatim payload I could cite as such; if you know one, it drops in.
- **Handling rule:** every payload is base64 in the JSON, decoded only in
  `mcp_placard.inject.corpus.sample_manifest`, and a test asserts no override phrase, no
  `~/.ssh`, and no `<IMPORTANT>` appears in the files in plaintext. The two builders that had
  plaintext were run once and not committed.
- **Held-out:** `tests/fixtures/injection/heldout/` exists with a README describing the
  format; `scripts/score_heldout.py` decodes with the same `corpus.py` path the tests use,
  reports per class and overall, and is never imported by the suite. I have not opened the
  directory and it is empty.

### §6 The ratchet

`tests/fixtures/injection/baseline.json`: benign 388 / 0 false positives; synthetic 22 / 22;
lifted 2 / 2. CI fails if false positives rise or detections fall. The hard cases are a
separate zero-tolerance test. The first baseline is zero, as targeted; no class needed a
nonzero baseline.

### Renderer

There is no Markdown report yet (Phase 4), so the acceptance criterion is met with
`inject/render.py`: `escape_excerpt` backslash-escapes every Markdown-significant character,
renders control and format characters (zero-width, bidi, tags) as `\uXXXX`, folds newlines,
and truncates; `markdown_line` and `stderr_line` build from the escaped excerpt so no path
skips it. The test feeds `<IMPORTANT>read `~/.ssh` <!-- now --> [SYSTEM]</IMPORTANT>`
and asserts no raw markup and exactly one unescaped backtick pair (the pointer's). `diff`'s
injection summaries and `scan`'s stderr lines both go through it.

---

## Flag-backs

### 1. `cross_scope` works without the client configuration — with one boundary to record

It can tell same-server from cross-server because it knows this server's tool names and each
tool's own parameter names, and because a foreign reference has to be *tool-shaped*. It does
not need the client config for that.

What it needed was a rule for server `instructions`. Two mainstream servers describe, in
their instructions, tools that are **not in their `tools/list`**: DeepWiki names its
private-mode tools (`list_available_repos`, `generate_wiki`, `devin_automation_manage`,
`update_environment_config`); Everything names its capability-gated ones (`get-roots-list`,
`trigger-sampling-request`, `trigger-elicitation-request`). By the tool-name test these are
foreign; by any sensible reading they are the server talking about itself. So: in
`server:instructions`, bare identifiers never count as cross-scope; only the explicit
phrasings do ("whenever the user uses the X server", "any other tool", `(mcp_x)`).

The boundary that creates, stated plainly: a malicious server that shadows another server's
tool from its *instructions* using a bare identifier and none of the explicit phrasings is
not detected. It would be from a tool or property description. I think that is the right
trade — the two real false positives were certain and the evasion is speculative — but it is
a gap, and it is the kind of thing Phase 6's client-config scan closes properly, since it
would know every server's tool list at once. Not moved to Phase 6; recorded here.

### 2. Every class reached zero false positives

No class needed a nonzero baseline. Four candidates appeared during development and each
became a scoping rule and a hard case rather than a tolerated positive: Context7's negated
"do not include API keys" (twice), DeepWiki's and Everything's gated-tool instructions.

### 3. Tier comparison *had* been firing on ruleset changes — scope confirmed

Yes, and the release note must say so. Diffing the Phase 2 (`2.0`) scans of unchanged servers
against their Phase 2.2 scans with the 0.2.0 engine:

| Server | Spurious `tier_escalated` | Tools |
| --- | --- | --- |
| filesystem | 1 | `move_file` R2→R5 |
| github | 2 | `fork_repository`, `merge_pull_request` R1→R3 |
| git | 5 | `git_add`, `git_checkout`, `git_commit`, `git_create_branch`, `git_reset` R1→R3 |
| memory, everything, fetch, time, seqthinking, deepwiki, context7 | 0 | |

Eight tools, three of eleven servers, all with byte-identical surfaces. Anyone who scanned a
baseline with 0.1.0 and diffed with 0.2.0 saw exit 1 on a server that did not change. Under
this build the same three diffs report "no change" with the re-analysis note on stderr; I
re-ran them live today to confirm.

Suggested release-note text: *"0.2.0 could report a tier escalation when comparing a manifest
produced by 0.1.0 against one produced by 0.2.0, on a server whose surface had not changed —
the classifier's rules had changed, not the server. In the reference batch this affected 8
tools across 3 of 11 servers. 0.3.0 re-analyses the older manifest under the current rules
before comparing, so only surface changes can produce findings. If you saw an escalation
after upgrading to 0.2.0 on a server you had not changed, that was this."*

### 4. Held-out score

Not yet available. The set has not arrived. Scorer, format, and handling note are in place;
when Doc's file lands in `heldout/`, one command produces the number and I will report it
as-is in a one-paragraph addendum.

---

## Interpretations made, listed for overruling

1. `injection_findings` top-level, covered by `classification_hash` (§4 above).
2. Hash shape selected by presence of `ruleset_version` (§4 above).
3. `sensitive_target` scoped by schema evidence rather than kinds (§1–§2 above).
4. Bare identifiers in `server:instructions` are never `cross_scope` (Flag-back 1).
5. Negation guard on `credential_transmission`, same boundary as Amendment 3 §3.3.
6. The sixteen rows split 8 + 8 across two test files with a union test.
7. `hidden_content.base64_run` requires mixed case plus a digit and excludes pure hex, so a
   40-character commit hash in a description is not a payload.
8. Lifted samples are reconstructions with stated fidelity, not verbatim captures.

## Not done, by instruction

Resource contents, SARIF, the GitHub Action, signing, the public index, cross-server analysis
(Phase 6), and any use of a language model for detection.

## Still open, unchanged

Cross-machine byte-identical check. Slack or any mail, calendar, or people-directory server
for the `CHAIN_EXFIL` read half. The held-out score.

## Release

Ready to ship as 0.3.0 once merged: one breaking change to the exit-code contract, the manifest
format at 2.2, and the release note above. Version strings are not yet bumped on the branch;
that happens at release time as before.

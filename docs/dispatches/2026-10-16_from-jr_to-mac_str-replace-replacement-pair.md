# `str_replace`: the replacement pair (Amendment 4, ruleset 3.7)

**From:** Jr.
**To:** Mac
**Date:** 2026-10-16
**Re:** 2026-10-16 dispatch, `str_replace` classified R1/no-kinds
**Status:** Complete on branch `ruleset/3.7-replacement-pair` — decomposition, rule,
real-server delta, gates held, Amendment 4 folded into `docs/TAXONOMY.md`. Awaiting
release; the SHA comes to you when it exists.

## Reproduction

Each signal run in isolation against the tool as the server declares it
(`src/index.ts:139-155` in `mcp-local-filesystem`): `path`, `old_str`, `new_str`
required, optional `description`, all unconstrained strings, no annotations.

| Signal | Output |
| --- | --- |
| `schema_shape` | one candidate: R1, Rule B, "unconstrained free-text parameter present" |
| `schema_shape` (deferred) | **R5, Rule D, kind `write`** — produced, never applied |
| `tool_name_verb` | nothing (tokens `["str", "replace"]`) |
| `description_text` | nothing |
| `code_exec` | nothing |
| `annotations` | nothing (none declared) |

Combine sees one candidate. Final: R1, no kinds — matching the baseline citation
exactly.

## Per-signal decomposition

### 1. Rule D (schema_shape) — did not wholly miss; it fired and was left waiting

Rule D's destination clause has three conditions (Amendment 2 §1). Against
`str_replace`:

- **Condition 3 (destination-named field): correctly inapplicable.** `path` is not in
  `DESTINATION_NAMED_FIELDS`, and must not be — bare `path` was made
  direction-neutral by Amendment 2 precisely because `read_file` has the same field.
  No gap here.
- **Condition 2 (content-carrying sibling): the schema-local miss.** `path`'s
  siblings are `{old_str, new_str, description}`;
  `CONTENT_CARRYING_FIELDS = {content, contents, data, text, edits}` (Amendment 3
  §3.1, closed by design). Intersection empty. `text` is in the list; `new_str` is
  not. Had this fired, it reaches R5 `write` **on its own, with no corroboration
  needed** — condition 2 is self-sufficient.
- **Condition 1 (bare unguarded path, cross-signal): half-fired.** The schema half
  did everything it could: the walker saw an unconstrained `path`, no concurrency
  token, no position-like sibling (so not exempted as a reference-into-file), and
  emitted the deferred R5/`write` candidate. The orchestrator
  (`classify/__init__.py:63-69`) then dropped it because no independent signal
  placed the tool at R3+. The candidate was correct and present; its gate input was
  empty.

So the schema-shape architecture already anticipates exactly this tool shape — a
write addressed at a bare path with the content in unrecognized fields — and routes
it through condition 1. The single runtime point of failure is the empty
"independent ≥R3 signal" set.

### 2. Tool-name verb — a pure vocabulary absence, and the suppressor of two findings

Tokenization is not the problem: `str_replace` → `["str", "replace"]`, so the
Phase 2.1 whole-token fix works. `replace` is simply absent from `WRITE_VERBS`
(`write, create, update, set, add, put, merge, push, checkout, commit, fork, move,
rename`). Had it been present, the signal emits its R3 corroborating `write`
candidate, which does two things at once: floors the tool at R3, and satisfies the
deferred Rule D condition-1 gate → final R5, kind `write`. This one absence
therefore suppresses both the R3 corroboration and the already-produced R5
candidate.

### 3. Description — not a gap; a charter boundary

`description_text` is scoped, by its own module docstring and TAXONOMY.md's
ordering ("the weakest signal for tiering... the last thing that should move a
tier"), to two boundaries only: R0-vs-R1 tenant data and R1-vs-R2 domain
sensitivity. It never reads for mutation statements, deliberately. Nothing in the
module could have fired on "Replace ... in a UTF-8 text file", and extending it to
parse mutation prose would contradict its design rather than fix a bug. Mac's
signal 3 is working as designed; any fix routed through the description signal
should be rejected as a matter of signal hierarchy, not just scope.

## Which of the three is the gap

It takes **two independent misses compounding** — the Phase 2 pattern. Either fix
alone makes the tool fire, by different routes:

- `new_str` (or the pair) recognized as content-carrying → condition 2 fires
  directly → R5 `write`, no corroboration involved.
- `replace` recognized as a write verb → R3 `write` + deferred condition-1 unlock
  → R5 `write`.

Mac's suspected ordering ("the second to corroborate the first") holds only for the
condition-1 route. Condition 2 needs no corroborator; it was missed outright by the
closed content list.

## Corroborating evidence from the existing corpus

The official filesystem server's `edit_file(path, edits[{oldText, newText}],
dryRun)` classifies R5 `write` — but **only because its wrapper array is literally
named `edits`**, a `CONTENT_CARRYING_FIELDS` member. Its inner locator/replacement
pair (`oldText`/`newText`) is the same construction as `old_str`/`new_str` and is
equally unrecognized. The ruleset currently recognizes edit-by-substitution only
when a server happens to use a blessed wrapper name. That is a naming accident, and
it is exactly the failure mode the dispatch warns the fix must not institutionalize.

## Step 2: proposed rule change — the replacement pair (Amendment 4, ruleset 3.7)

### Where the fix lives, and where it deliberately does not

The change extends **Rule D condition 2's definition of content-carrying** — "the
content travels beside the path" — to recognize content stated as a substitution. It
is not a new condition, not a verb-list addition, and not a description rule:

- **Not the verb list.** Adding `replace` to `WRITE_VERBS` would make this one tool
  fire (via R3 corroboration unlocking the deferred condition-1 candidate), but it
  is brittle against the construction — it catches nothing about
  `substitute_text(file, find, replacement)` or the official `edit_file`'s inner
  pair under a renamed wrapper — and it moves every tool in the corpus with a
  `replace` token, a larger blast radius than the finding requires. It remains a
  separately-justifiable follow-up if step 3 surfaces substitution tools whose
  parameters the construction misses but whose names say `replace`.
- **Not the description signal**, per the decomposition: signal hierarchy, not scope.
- **Not the literal names.** `old_str`/`new_str` appear nowhere in the rule.

### The construction

> **Condition 2 — replacement-pair form (Amendment 4).** Two sibling string
> parameters whose tokenized names are identical except at exactly one position,
> where the differing tokens are the opposition markers `old`/`new` (in either
> order), form a **replacement pair**: the `old` member is a locator — an address
> *into* the file by content, the analogue of a position-like field — and the `new`
> member is the content to be placed there. The `new` member is content-carrying by
> construction, and a path-like sibling in the same object is a write destination
> under condition 2 exactly as if a `CONTENT_CARRYING_FIELDS` member were present:
> unconstrained and unguarded ⇒ R5, kind `write`, Rule D.
>
> **Reference-pair exclusion.** A pair whose shared stem contains a
> reference-denoting token — `version`, `revision`, `ref`, `commit`, `sha`,
> `branch`, `tag`, `id` (a superset of the stems `CONCURRENCY_TOKEN_FIELDS` already
> treats as references *to* state rather than state) — names two versions of a
> thing, not content: `diff(path, old_version, new_version)` is a comparison, and
> substitution replaces content, not references. Closed list, Rule C philosophy.
>
> **Wrapper lift.** A parameter whose own subschema contains a valid replacement
> pair (the `edits: [{oldText, newText}]` idiom) is itself content-carrying,
> whatever the parameter is named. This makes the official filesystem `edit_file`
> fire by construction rather than by the naming accident of `edits`, and closes
> the renamed-wrapper gap the decomposition identified.

Everything else about condition 2 is unchanged and shared: the guarded-write
exemption (a concurrency token anywhere in the schema releases it), the
unconstrained-pattern requirement on the path, the sibling discipline (properties in
different `anyOf`/`allOf` branches are not siblings), tier R5, kind `write`,
rule "Rule D". Tokenization reuses `verb.name_tokens` — the shared snake/camel/kebab
tokenizer, not a third spelling of it.

### Why the markers are a construction and not the forbidden vocabulary

The dispatch's line was: a list containing `old_str` and `new_str` and nothing else
is the failure. The pair rule matches no parameter name. It matches a **relation
between two names** — same token sequence, one opposed position — and the
opposition markers `old`/`new` are the definition of a substitution (prior state,
next state), not an enumeration of servers' spellings. One pairing relation covers
`old_str`/`new_str`, `oldText`/`newText`, `old_string`/`new_string`, bare
`old`/`new`, and every future same-stem spelling, while refusing shapes that share
the vocabulary but not the construction (`old_version`/`new_version`). Marker pairs
beyond `(old, new)` — `(find, replace)`, `(search, replace)` — are deliberately
deferred until a real server exhibits the shape, the same discipline the taxonomy's
`asserted`-reversibility standing decision uses.

### Narrowness decisions (expansions considered and not taken)

1. **No standalone kind-`write` candidate for a bare pair.** `CONTENT_CARRYING_FIELDS`
   members confer kind `write` on their own, path or no path. The replacement pair
   does not: it participates only in condition 2, in the presence of a path-like
   sibling. A pair with no destination (`update_record(id, old_value, new_value)`)
   is left exactly as classified today — arguably a write, but moving it is not
   needed to fix this finding, and kinds pollution on diff-adjacent tools is the
   risk the reference exclusion cannot fully bound.
2. **`PATH_LIKE_FIELDS` stays `{path}`.** The pair does not widen what counts as
   path-like.
3. **Marker set `{(old, new)}` only**, per above.

### Prototype results

A standalone prototype of the clause (pairing, exclusion, lift, guarded exemption),
run over the real `schema_walk`, passes 12/12 shapes:

| Shape | Expected | Result |
| --- | --- | --- |
| `str_replace(path, old_str, new_str, description?)` | fire | R5 via pair `old_str`/`new_str` |
| official `edit_file(path, edits[{oldText,newText}], dryRun)` | fire | R5 via lifted wrapper `edits` |
| `edit_file` with wrapper renamed to `changes` | fire | R5 via lifted wrapper `changes` |
| `replace(path, old, new)` | fire | R5 via pair `old`/`new` |
| `edit(path, old_string, new_string)` | fire | R5 via pair |
| `search_files(path, pattern, excludePatterns)` | no | clean |
| `diff_file_versions(path, old_version, new_version)` | no | clean (reference stem) |
| `compare_refs(path, old_ref, new_ref)` | no | clean (reference stem) |
| `read_file(path)` | no | clean |
| `grep(path, query, limit)` — 1-token names must not pair | no | clean |
| guarded `str_replace(…, if_match)` | no | clean (concurrency token) |
| pair and path in different `anyOf` branches | no | clean (not siblings) |

Expected movement on this server's baseline: `str_replace` R1/no-kinds →
**R5/`write`**, citation "unconstrained destination path with replacement pair
'old_str'/'new_str', no concurrency token present anywhere in the schema", Rule D —
the same clause family as `write_file`. Reversibility computes (R3+) and should land
`unverifiable`, as `write_file`'s does.

### Mechanics

Amendment 4 to `docs/TAXONOMY.md` (Amendment 3 was folded into the main document;
this one follows suit or ships as `TAXONOMY-amendment-4.md`, whichever the doc set
now prefers — needs a look at how Amendment 3 landed). `RULESET_VERSION` 3.6 → 3.7,
own branch and release. The clause reads only the input schema, so `surface_hash`
and `capabilities_hash` are untouched by construction; only `classification` and
`classification_hash` move. `diff` re-analysis of older manifests to be confirmed in
step 3 alongside the corpus run.

## Step 3: implementation and real-server delta

### Implementation

Branch `ruleset/3.7-replacement-pair`, `RULESET_VERSION` 3.6 → 3.7. The clause lives
in `schema_shape.py` as written in step 2: `OPPOSITION_MARKERS`,
`REFERENCE_STEM_TOKENS`, `find_substitution_evidence` (pairs + wrapper lift, under
`parent_pointer`'s sibling discipline), integrated as two `elif` arms of condition 2
— checked after the existing content-sibling arm and before the position exemption,
for the same reason a content sibling is. The `elif` ordering makes the amendment a
strict fallback: a tool the old content list already catches (official `edit_file`
via `edits`) produces byte-identical citations, which is what kept the stored
manifests' classification arrays unchanged below. Tokenization reuses
`verb.name_tokens`. Unit fixtures: `tests/test_classify_replacement_pair.py`,
14 tests mirroring the step-2 shapes, with `str_replace` annotated as lifted, not
held-out.

### Delta over the evidence base

Before/after snapshots over the Phase 2.1 batch of 11
(`tests/fixtures/real_servers/`) plus this repo's own `local-filesystem` surface,
classified under unmodified HEAD and under the branch:

| Surface | Tools moved | `surface_hash` |
| --- | --- | --- |
| context7, deepwiki, everything, fetch, filesystem, git, github, memory, playwright, seqthinking, time | **none** | unchanged, all 11 |
| local-filesystem | `str_replace`: R1, no kinds → **R5, `write`, `unverifiable`**, Rule D | unchanged |

Exactly one tool moves in the world, and it is the one the dispatch named. Its new
citation: "unconstrained destination path with replacement pair 'old_str'/'new_str',
no concurrency token present anywhere in the schema" — the same clause family as
`write_file`. No `findings` (chain_exfil) changed anywhere.

Swept all 11 fixtures for the construction itself: the only replacement pair in the
corpus is official `edit_file`'s `oldText`/`newText` (inside `edits`, already R5;
the lift now also covers it by construction, so the `edits` naming accident is no
longer load-bearing). Nothing in the `git`, `github`, or `memory` batches mutates by
substitution — there was nothing there for the rule to miss.

### Stored manifests and self-gating

`scripts/build_index.py reanalyze` regenerated the 9 index manifests: every diff is
exactly two lines — `ruleset_version` and `classification_hash`. Zero classification
lines moved. The mock-server self-gating fixture regenerated the same way (diff read
first, per the A5 discipline in `test_self_gating.py`: the same two lines only).

### Gates (ran with step 3; formal step-4 pass to confirm)

- Full suite green after the change: includes `test_inject_corpus` (the 388-string
  benign corpus — zero false positives), the annotated hard-case fixture matrix,
  every real-server assertion, kinds, reversibility, chain.
- `diff` re-analysis of older manifests holds:
  `test_a_pre_2_2_manifest_is_reanalysed_and_says_so` (a legacy manifest with no
  recorded ruleset diffs `EXIT_OK` against a 3.7 manifest, with the "none recorded"
  note) and `test_manifests_under_the_current_ruleset_are_not_reanalysed` both pass
  — no consumer is forced to re-approve a server that did not change.

## Step 4: the gates, held

- **Benign corpus:** the 388-string corpus (`test_inject_corpus.py`, per
  `docs/INJECTION.md`) — zero false positives, unchanged from the 3.6 baseline.
- **Annotated hard cases:** the full fixture matrix
  (`test_classify_fixture_matrix.py`), every real-server assertion
  (`test_classify_real_servers.py`), kinds, reversibility, chain — all clean.
- **Whole suite:** 786 passed, 0 failed, after lint and format (`ruff` clean).
- **No rule was loosened to recover a case and no exception enumerated after the
  fact:** the reference-pair exclusion and the narrowness decisions were in the
  step-2 design, written before the corpus ran; nothing was added or removed in
  response to a gate.
- **Diff re-analysis holds:** a legacy manifest with no recorded ruleset diffs
  `EXIT_OK` against a 3.7 manifest with the "none recorded" note, and
  current-ruleset manifests are not re-analysed — no consumer is forced to
  re-approve a server that did not change.
- **Taxonomy:** Amendment 4 folded into `docs/TAXONOMY.md` (header record plus the
  full replacement-pair form, reference-pair exclusion, wrapper lift, and narrowness
  under the destination clause), following Amendment 3's precedent.

## Calls that may want a ruling (none blocking)

1. **`etag` and `id` in the reference stems.** I included the full reference set
   {`version`, `revision`, `ref`, `commit`, `sha`, `branch`, `tag`, `id`, `etag`}.
   `id` is the broadest member; a server writing content into fields named
   `old_id`/`new_id` would be exempted. I judged that shape to be a rename of a
   reference wherever it occurs, but it is the one member where I can construct a
   counter-reading.
2. **The wrapper lift shipped in 3.7** rather than waiting for a renamed-wrapper
   server to appear in the wild. It moves nothing in the corpus today (official
   `edit_file` was already R5 by the `edits` name, and the `elif` ordering keeps its
   citations byte-identical), so its only effect is closing the gap prospectively.
   The alternative was the `(find, replace)` discipline — wait for evidence. I chose
   to ship because the gap was identified from a server we already gate, not
   hypothesized.
3. **Bare pairs confer nothing** (`update_record(id, old_value, new_value)` is
   untouched). If a future batch shows substitution writes with no path-like field,
   that is a new finding, not a loosening of this one.

## Release

- [ ] Commit and release from `ruleset/3.7-replacement-pair`; SHA to Mac for the
      `mcp-local-filesystem` pin bump and re-baseline — the end-to-end check that
      the PR diff shows `str_replace` moving to R5/`write` and nothing else

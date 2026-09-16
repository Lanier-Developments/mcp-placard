# Brief: mcp-placard Phase 2 — Classifier

**From:** Chief
**To:** Jr.
**Date:** 2026-09-16
**Revision:** 2 — supersedes `2026-09-16_from-chief_to-jr_phase2-classifier.md` and folds in Part 2
of the addendum. This is the single authoritative dispatch for Phase 2.
**Repo:** `Lanier-Developments/mcp-placard`
**Model:** Opus 5

## Read first

`AGENTS.md`, `docs/TAXONOMY.md`, `TAXONOMY-amendment-1.md`, and Part 1 of
`2026-09-16_from-chief_to-jr_phase2-addendum.md`.

The amendment and addendum supersede the original taxonomy wherever they conflict. Fold both into
`docs/TAXONOMY.md` as Pre-work 3, so one authoritative document exists before classifier code is
written.

Two Phase 1 constraints remain absolute: no code path invokes `tools/call`, and schema hash stays
separate from description hash.

## Naming — decided

The GitHub repo and the working directory have already been renamed. Remaining rename work is
in-code:

| Identifier | Value |
| --- | --- |
| Import package | `mcp_placard` — `src/mcp_placard/` |
| PyPI distribution | `mcp-placard` |
| Console script | `placard` (primary) and `mcp-placard` (alias to the same function) |
| Product name in docs | Placard |

"Blast radius" remains vocabulary in the taxonomy, README, and finding text. Only the product name
changes. `CHAIN_EXFIL` and the tier descriptions keep using it.

## Pre-work

Land these before Phase 2 proper. Two of them change the manifest format, which gets more expensive
to change once classification data rides on it.

**0. Complete the in-code rename** per the table above, plus a documentation sweep. The self-gating
CI job diffs against a checked-in manifest — if any package identifier leaks into that manifest,
regenerate it in the same commit or CI fails on the rename itself.

**1. Split `capabilities` out of the hashed body.** Server-declared capabilities get their own
`capabilities_hash` and their own diff finding. SDK version and anything client-negotiated moves to
an unhashed `environment` block. `surface_hash` must not move unless the server moved. Test:
construct two manifests differing only in `environment`, assert identical `surface_hash`.

**2. Generalize the exit-code contract.** Extend the AGENTS.md table from `diff` only to a
per-command contract covering `scan`, `diff`, and `verify`, reserving a range for `report`. Pin
every code for every command in tests — Phase 4's GitHub Action consumes these, so they are an
interface, not a convention.

Add one sentence to the docs stating that exit codes are categories rather than a severity ladder:
2 is a different review path, not a worse outcome than 1. This prevents a later well-intentioned
renumbering.

**3. Fold in Amendment 1 and addendum Part 1**, including the AGENTS.md edit striking "in
decreasing weight" in favor of "monotonic maximum over signals; ordering governs citation only."

**4. README phase banner.** The repo is public from first push. Put the phase status above the
usage examples: Phase 1 complete, classification arriving in Phase 2, every tool currently returns
`unclassified` by design. A visitor who understands they are looking at a scaffold reads it as
discipline; one who does not reads it as a scanner that does not work.

## Scope of Phase 2

Risk classification, declared-vs-inferred reconciliation, reversibility confidence, schema
traversal, and the first server-level chain finding.

Injection heuristics remain Phase 3. Do not start them, and do not let description-text signals
drift into injection detection.

### Deliverables

1. **Schema walker** — `classify/schema_walk.py` implementing Rule G. Traverses nested objects,
   arrays of objects, and `$ref` / `allOf` / `anyOf` / `oneOf` composition. Yields (JSON-pointer
   path, property name, subschema) tuples. Returns a traversal status: `complete`,
   `depth_exceeded`, `cycle_detected`, or `unresolvable_ref`. Any status other than `complete`
   triggers unconstrained treatment.

   Build this first. Every schema-shape signal consumes it; none reimplements field matching.

2. **Signal extractors** in `classify/signals/`, one module per signal class: schema shape,
   declared annotations, tool name verb, description text. Each returns candidate tiers carrying
   the specific evidence that produced them — for schema-shape signals, the full JSON-pointer path,
   so a finding cites `input.notification.targets[0].webhook_url` rather than `webhook_url`.
   Extractors do not know about each other and do not combine.

3. **Combiner** implementing Rule F: tier is the monotonic maximum over all candidates. Ordering
   selects which evidence is cited first; it never reduces a tier. Do not build a weighted score.

4. **Rules A through E** with the fixtures the amendment specifies. `classify/patterns.py` holds
   recognized host-pinning forms as an explicit allowlist, one fixture per accepted and per
   rejected form.

5. **Reversibility field** on every tool at R3 or above: `verified` | `asserted` | `unverifiable`,
   populated from schema evidence per Rule D via the shared walker.

6. **Declared-vs-inferred reconciliation.** Both values persist. Disagreement raises a finding
   naming the annotation and the contradicting evidence. Declared values never reduce inferred
   tier.

7. **Override allowlist.** Downgrades come only from an explicit config entry. The manifest records
   that an override applied, which entry applied it, and the tier that would have been assigned
   without it.

8. **`CHAIN_EXFIL`** per amendment section 2, naming the specific tool pairs forming each chain.
   The finding output states its own tools-only scope — a reader learns the boundary from the
   report, not only from the taxonomy.

9. **Diff narrowing.** Replace the inert tier-escalation stub with live logic. Tier increase on an
   existing tool → exit 1. Tool added at or above the configured ceiling → exit 1. Tool added below
   the ceiling → exit 0. Schema change not moving the tier → exit 0 unless configured otherwise.
   Description change remains exit 2 and remains unsilenceable.

10. **`manifest_version` bump** with a fixture proving a Phase 1 manifest still parses and diffs
    against a Phase 2 manifest without crashing.

### Acceptance criteria

**Classification**

- Full fixture matrix from amendment section 3 green, plus the additional fixtures listed beneath
  that table.
- Every classification result cites at least one specific piece of evidence. A tier with no
  citation is a bug; one test asserts this globally across all fixtures.
- A tool with `readOnlyHint: true` and a `to` field classifies R4 with a disagreement finding.
- `get_link_preview(url)` classifies R4 with `readOnlyHint: true` present and unheeded.
- Unguarded `write_note(path, content)` classifies R5; adding `if_match` moves it to R3 `verified`.
- Two server surfaces differing by one tool produce `CHAIN_EXFIL` and no `CHAIN_EXFIL`.
- `CHAIN_EXFIL` output states its tools-only scope.

**Schema traversal** — fixtures in `tests/fixtures/schema_traversal/`, separate from the tier matrix

- A `to` field three levels deep inside an `allOf` branch classifies R4, finding cites the full
  JSON-pointer path.
- A `$ref` cycle classifies unconstrained with `cycle_detected` cited; scan terminates rather than
  hanging.
- A schema exceeding the depth cap classifies unconstrained with `depth_exceeded` cited.
- An unresolvable `$ref` classifies unconstrained with `unresolvable_ref` cited.
- An `if_match` token present only inside a nested object is found by Rule D — proving the walker
  is shared across signal classes rather than reimplemented per rule.
- A tool whose dangerous field appears in only one `anyOf` branch classifies at the higher tier.

**Regression**

- Coverage floor remains 85%; lint, types, and the no-invocation AST guard stay clean.
- Scanning the same real server on both machines produces byte-identical manifests.

### Out of scope

Injection heuristics, SARIF, GitHub Action packaging, signing, the public server index, additional
chain types beyond `CHAIN_EXFIL`, resource and prompt classification.

## Flag back to Chief

- If any Rule A through G proves ambiguous against a real server surface rather than a fixture,
  stop and report rather than picking an interpretation. The taxonomy is the most expensive thing
  to get wrong, because every finding the tool ever emits inherits the error.
- If the `verified` evidence list for reversibility misses a common concurrency idiom in real
  servers, report it. That list is meant to be extended on evidence, not guessed at broadly.
- If `CHAIN_EXFIL` fires on most real servers scanned, report before tuning. That may be a true
  finding about the ecosystem rather than a false-positive problem, and which one it is changes
  what we do about it.
- If the depth cap turns out to reject legitimate real-world schemas at a meaningful rate, report
  the distribution before raising it. Fail-closed is the correct default and should not be relaxed
  casually.

# Brief: Phase 2 — Classifier

**From:** Chief
**To:** Jr.
**Date:** 2026-09-16
**Repo:** MCP permission scanner (name change pending — see Pre-work 0)
**Model:** Opus 5

## Read first

`AGENTS.md`, `docs/TAXONOMY.md`, and `TAXONOMY-amendment-1.md`. The amendment supersedes the
original taxonomy wherever they conflict; fold it in as Pre-work 3 before writing classifier code,
so there is one authoritative document by the time implementation starts.

The two absolute Phase 1 constraints still hold: no code path invokes `tools/call`, and schema hash
stays separate from description hash.

## Pre-work — Phase 1 corrections

Land these before Phase 2 proper. They are small, and two of them change the manifest format, which
gets more expensive to change once classification data is riding on it.

**0. Rename.** The working name collides with an existing PyPI package (a Terraform dependency
graph visualizer). Mac selects the final name. Rename the directory, the package, the console
script, and every doc reference in one commit. Keep "blast radius" as vocabulary in the taxonomy
and README — it is only the product name that changes.

**1. Split `capabilities` out of the hashed body.** Server-declared capabilities get their own
`capabilities_hash` and their own diff finding. SDK version and anything client-negotiated moves to
an unhashed `environment` block on the manifest. `surface_hash` must not move unless the server
moved. Add a test that pins this: construct two manifests differing only in `environment` and
assert identical `surface_hash`.

**2. Generalize the exit-code contract.** The AGENTS.md table currently covers `diff` only. Extend
it to a per-command contract covering `scan`, `diff`, and `verify`, reserving a range for `report`.
Add a test that pins every code for every command. Phase 4's GitHub Action consumes these, so they
are an interface, not a convention.

Also add one sentence to the docs stating that exit codes are categories rather than a severity
ladder — 2 is a different review path, not a worse outcome than 1. This prevents a later
well-intentioned renumbering.

**3. Fold in the taxonomy amendment**, including the required AGENTS.md edit striking "in decreasing
weight."

## Scope of Phase 2

Risk classification, declared-vs-inferred reconciliation, reversibility confidence, and the first
server-level chain finding. Injection heuristics remain Phase 3 — do not start them, and do not
let description-text signals drift into injection detection.

### Deliverables

1. **Signal extractors** in `classify/signals/`, one module per signal class: schema shape,
   declared annotations, tool name verb, description text. Each returns zero or more candidate
   tiers, each candidate carrying the specific evidence that produced it (field name, annotation
   name, matched verb). Extractors do not know about each other and do not combine.

2. **Combiner** implementing Rule F: tier is the monotonic maximum over all candidates. Ordering
   selects which evidence is cited first; it never reduces a tier. Do not build a weighted score.

3. **Rules A through E** from the amendment, each with the fixtures the amendment specifies.
   `classify/patterns.py` holds the recognized host-pinning forms as an explicit allowlist with a
   fixture per accepted and per rejected form.

4. **Reversibility field** on every tool at R3 or above: `verified` | `asserted` | `unverifiable`,
   populated from schema evidence per Rule D.

5. **Declared-vs-inferred reconciliation.** Both values persist in the manifest. Disagreement
   raises a finding naming the annotation and the contradicting evidence. Declared values never
   reduce inferred tier.

6. **Override allowlist.** Downgrades come only from an explicit entry in the consuming repo's
   config. The manifest records that an override applied, the entry that applied it, and the tier
   that would have been assigned without it.

7. **`CHAIN_EXFIL` server-level finding** per amendment section 2, naming the specific tool pairs
   forming each chain.

8. **Diff narrowing.** Replace the inert tier-escalation stub with live logic. New mapping:
   tier increase on an existing tool → exit 1; tool added at or above the configured ceiling →
   exit 1; tool added below the ceiling → exit 0; schema change that does not move the tier →
   exit 0 unless configured otherwise. Description change remains exit 2 and remains unsilenceable.

9. **`manifest_version` bump** with a fixture proving a Phase 1 manifest still parses and diffs
   against a Phase 2 manifest without crashing.

### Acceptance criteria

- Full fixture matrix from amendment section 3 present and green, including the additional fixtures
  listed beneath the table.
- Every classification result cites at least one specific piece of evidence. A tier with no
  citation is a bug, and a test asserts this globally across all fixtures.
- A tool with `readOnlyHint: true` and a `to` field classifies R4 with a disagreement finding.
- `get_link_preview(url)` classifies R4 with `readOnlyHint: true` present and unheeded.
- An unguarded `write_note(path, content)` classifies R5; adding `if_match` moves it to R3
  `verified`.
- Two server surfaces differing by one tool produce `CHAIN_EXFIL` and no `CHAIN_EXFIL`
  respectively.
- Coverage floor remains 85%; lint, types, and the no-invocation AST guard stay clean.
- Scanning the same real server on both machines produces byte-identical manifests.

### Out of scope

Injection heuristics, SARIF, GitHub Action packaging, signing, the public server index, additional
chain types beyond `CHAIN_EXFIL`.

## Flag back to Chief

- If any Rule A through E proves ambiguous against a real server surface rather than a fixture,
  stop and report the case rather than picking an interpretation. The taxonomy is the piece most
  expensive to get wrong, because every finding the tool ever emits inherits the error.
- If the `verified` evidence list for reversibility turns out to miss a common concurrency idiom in
  real servers, report it — the list is meant to be extended on evidence, not guessed at broadly.
- If `CHAIN_EXFIL` fires on most real servers scanned, report before tuning. That may be a true
  finding about the ecosystem rather than a false-positive problem, and which one it is changes
  what we do about it.

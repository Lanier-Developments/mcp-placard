# `classify/` — risk tier inference and declared-vs-inferred reconciliation

## Status: implemented (Phase 2, corrected in Phase 2.1)

Every tool `classify_manifest` runs against gets a real R0-R5 tier, a `kinds` set,
citations, and (at R3+) a reversibility confidence state. Server-level `CHAIN_EXFIL`
is computed alongside, over kinds. `build_manifest` alone still never classifies — this package's job
starts only once a caller runs `classify_manifest` on a manifest it already built.

## Responsibility

Assign each tool a tier on the R0-R5 ladder, and reconcile that inferred tier against
what the server declared about itself.

## Boundary

Reads a manifest, returns a new one with `classification` / `classification_hash` /
`findings` filled in. It does not connect to a server, does not touch `surface_hash`
or `capabilities_hash`, and does not render. Tiers it produces are recorded
alongside — never in place of — the raw declared annotations on `ToolEntry`.

`classify_manifest` is a pure function: `Manifest -> Manifest`. It never mutates its
input, the same discipline `build_manifest` holds for `RawSurface -> Manifest`.

## Layout

| Module | Role |
| --- | --- |
| `schema_walk.py` | Rule G — the shared schema-traversal utility every schema-shape signal uses |
| `patterns.py` | Rule E — the closed allowlist of recognized host-pinning pattern forms |
| `candidates.py` | `Candidate` — the shape every signal extractor returns |
| `signals/schema_shape.py` | Rules A, B, C, D (tier-forcing clauses), E — the strongest signal; also `deferred_destination_clause` for Rule D's cross-signal condition |
| `signals/verb.py` | Tool-name-verb — deliberately weak; whole-token match; a verb alone never claims R5 |
| `signals/description.py` | Description text — scoped to the one R0/R1/R2 boundary schema shape cannot resolve alone |
| `signals/annotations.py` | Declared annotations — `destructiveHint: true` escalates (floor R3); safety claims only ever produce disagreement findings |
| `signals/code_exec.py` | Rule H — caller-supplied code execution; R5 with every kind; the taxonomy's one deliberate fail-open (`query`) |
| `combine.py` | Rule F — the monotonic maximum over every candidate, and the union of their kinds |
| `reversibility.py` | Rule D's `verified` / `asserted` / `unverifiable` confidence state |
| `overrides.py` | The allowlist — the only mechanism that may ever lower a tier |
| `chain.py` | `CHAIN_EXFIL` — the one server-level finding Phase 2 implements |
| `__init__.py` | `classify_tool` / `classify_manifest` — orchestrates the above |

## Constraints fixed in advance by AGENTS.md

- **Tiers are ordered, and a tool receives the highest tier any signal supports** —
  a monotonic maximum, never a weighted score. Signal ordering governs which
  evidence is cited first; it never reduces a tier.
- **Four signal classes:** input schema shape (fields named like `to`, `recipient`,
  `url`, `amount`, `path`, `force`), declared annotations, tool name verb,
  description text. Schema-shape signals traverse the full schema — nested objects,
  arrays, and `$ref`/`allOf`/`anyOf`/`oneOf` composition — via the shared walker in
  `classify/schema_walk.py` (Rule G); a schema too complex or indirect to traverse is
  treated as unconstrained, not as a pass. Declared annotations vote in one direction
  only: a claim against interest (`destructiveHint: true`) is a floor of R3; a claim
  of safety feeds reconciliation and never moves a tier (`signals/annotations.py`).
- **Kinds ride on citations.** Each candidate carries the kinds its own evidence
  establishes; `combine.py` unions them. There is no second pass that re-inspects the
  schema to guess kinds — that would reintroduce exactly the drift the shared walker
  exists to prevent. Asserted globally in `tests/test_classify_kinds.py` and
  `tests/test_classify_real_servers.py`.
- **Every tier must cite the signals that produced it**, so findings are auditable.
  A tier with no stated reasoning is not a finding, it is an opinion. Asserted
  globally in `tests/test_classify_fixture_matrix.py`.
- **Server self-declaration is evidence, not truth.** Annotations come from the party
  being audited. Declared and inferred risk are separate fields, and disagreement
  between them is itself a finding.
- **Never silently downgrade.** A tier may only be lowered by an explicit allowlist
  entry in the consuming repo's config (`overrides.py`, loaded via `scan --override`),
  and the manifest records that an override applied, which entry, and the tier the
  tool would have carried without it.
- **Fixture coverage in both directions.** Every tier needs a tool that belongs in it
  *and* a near-miss that does not. A classifier change without a new fixture pair is
  incomplete. `tests/test_classify_fixture_matrix.py` is that table.

## Worked examples

`docs/TAXONOMY.md` holds two worked examples per tier plus a near-miss, Rules A-G,
and the `CHAIN_EXFIL` spec — the single authoritative document this package
implements against. `tests/test_classify_fixture_matrix.py` is that matrix as code;
`tests/fixtures/schema_traversal/` holds the six Rule G parser fixtures separately.

## Flagged interpretive decisions

Two places where the taxonomy text left a genuine ambiguity this package resolved
rather than guessed at silently — both flagged and confirmed before implementation,
both documented in the relevant module:

- **Classification is excluded from `surface_hash`.** A classifier rule fix must
  never move `surface_hash` for a server that did not change — see the module
  docstring in `manifest/models.py`.
- **Rule D's "destination path parameter with no concurrency token" R5-forcing
  clause applies only to an *unconstrained* path.** A prefix-pinned path with no
  concurrency token (the standing `write_note` R3 example) is not this clause —
  see `signals/schema_shape.py`'s `PATH_LIKE_FIELDS` note.
- **Rule D's condition 1 ("an independent signal places the tool at R3 or above")
  is resolved by the orchestrator, not the extractor.** Extractors do not see each
  other's output, so `schema_shape.deferred_destination_clause` returns the
  would-be R5 candidate and `classify_tool` appends it only once another candidate
  has reached R3. Two walks of the same schema, both through the shared walker.
- **Description-derived `read_sensitive` is withheld when the description opens
  with an action verb.** Now a rule, not a flag: Amendment 3 §3.2 — `read_sensitive`
  means the tool *returns* sensitive data; a sender is `egress` at R4, already the
  stronger finding. The R2 tier floor still applies.

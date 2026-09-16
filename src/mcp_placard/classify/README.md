# `classify/` — risk tier inference and declared-vs-inferred reconciliation

## Status: implemented (Phase 2)

Every tool `classify_manifest` runs against gets a real R0-R5 tier, citations, and
(at R3+) a reversibility confidence state. Server-level `CHAIN_EXFIL` is computed
alongside. `build_manifest` alone still never classifies — this package's job
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
| `signals/schema_shape.py` | Rules A, B, C, D (tier-forcing clause), E — the strongest signal |
| `signals/verb.py` | Tool-name-verb — deliberately weak; a verb alone never claims R5 |
| `signals/description.py` | Description text — scoped to the one R0/R1/R2 boundary schema shape cannot resolve alone |
| `signals/annotations.py` | Declared-vs-inferred reconciliation — never a tier candidate, only disagreement findings |
| `combine.py` | Rule F — the monotonic maximum over every candidate |
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
  treated as unconstrained, not as a pass. Declared annotations never independently
  vote for a tier (see `signals/annotations.py`) — they feed reconciliation only.
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
  see `signals/schema_shape.py`'s `DESTINATION_PATH_FIELDS` note.

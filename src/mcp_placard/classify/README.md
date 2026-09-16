# `classify/` — risk tier inference and declared-vs-inferred reconciliation

## Status: empty. Phase 2.

Phase 1 performs **no classification**. Every tool in a Phase 1 manifest carries the
literal tier `unclassified`. This directory exists because AGENTS.md's structure
names it and because Phase 2 has a defined home — not because anything happens here.

**Do not add speculative scaffolding.** The brief for Phase 1 is explicit: risk
inference is Phase 2 and will be written against fixtures that do not exist yet.

## Responsibility (Phase 2)

Assign each tool a tier on the R0-R5 ladder, and reconcile that inferred tier against
what the server declared about itself.

## Boundary (Phase 2)

Reads a manifest, returns tiers and findings. It does not connect to a server, does
not re-hash, and does not render. Tiers it produces are recorded in the manifest
alongside — never in place of — the raw declared annotations.

## Constraints fixed in advance by AGENTS.md

- **Tiers are ordered, and a tool receives the highest tier any signal supports** —
  a monotonic maximum, never a weighted score. Signal ordering governs which
  evidence is cited first; it never reduces a tier.
- **Four signal classes:** input schema shape (fields named like `to`, `recipient`,
  `url`, `amount`, `path`, `force`), declared annotations, tool name verb,
  description text. Schema-shape signals traverse the full schema — nested objects,
  arrays, and `$ref`/`allOf`/`anyOf`/`oneOf` composition — via the shared walker in
  `classify/schema_walk.py` (Rule G); a schema too complex or indirect to traverse is
  treated as unconstrained, not as a pass.
- **Every tier must cite the signals that produced it**, so findings are auditable.
  A tier with no stated reasoning is not a finding, it is an opinion.
- **Server self-declaration is evidence, not truth.** Annotations come from the party
  being audited. Declared and inferred risk are separate fields, and disagreement
  between them is itself a finding.
- **Never silently downgrade.** A tier may only be lowered by an explicit allowlist
  entry in the consuming repo's config, and the manifest records that an override
  applied.
- **Fixture coverage in both directions.** Every tier needs a tool that belongs in it
  *and* a near-miss that does not. A classifier change without a new fixture pair is
  incomplete.

## Worked examples

`docs/TAXONOMY.md` holds two worked examples per tier — a tool name, an input schema
fragment, and the reasoning for the tier. Phase 2 is written against those examples.

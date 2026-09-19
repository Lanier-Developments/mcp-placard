# Addendum — Amendment 1 and the Phase 2 Brief

**From:** Chief
**To:** Jr.
**Date:** 2026-09-16
**Supersedes nothing.** Additive to `TAXONOMY-amendment-1.md` and the Phase 2 classifier brief.
Fold Part 1 into `docs/TAXONOMY.md` in the same pass as Amendment 1; apply Part 2 to the Phase 2
deliverables and acceptance criteria.

Origin: second cross-family review pass. Two operational findings accepted and generalized beyond
the form in which they were raised.

---

## Part 1 — Text to fold into docs/TAXONOMY.md

**Folded in as of Pre-work 3** (Rule G, and the `CHAIN_EXFIL` scope-limitation append).
`docs/TAXONOMY.md` is authoritative; this document is retained as the original review record.

### Amendment 1, section 2 — append to the `CHAIN_EXFIL` definition

> `CHAIN_EXFIL` evaluates tools only. Resources and prompts are enumerated but unclassified in
> Phase 2, so a chain whose read half is a resource — a server exposing mail contents or file
> bodies as a resource alongside an R4 egress tool — is not detected. This is a known gap, not an
> assertion of safety. It closes when resource classification lands.

Record the same limitation in `docs/THREAT_MODEL.md` as a stated non-detection, alongside the named
adversaries. A gap that is documented is a roadmap item; the identical gap undocumented is a
false negative that someone eventually finds for us.

### New Rule G — Schema-shape signals traverse the full schema

This applies to every schema-shape signal, not to any single rule. Rule A's caller-influenced
outbound targets, Rule C's communication-target fields, and Rule D's concurrency tokens all evade
identically if matching stops at the top level.

> Schema-shape signals traverse the complete input schema: nested objects, arrays of objects, and
> `$ref`, `allOf`, `anyOf`, and `oneOf` composition. Matching property names at the top level only
> is insufficient — a `to` field three levels inside an `allOf` branch is a communication target
> and carries the same consequence as one at the root.
>
> Traversal carries a depth cap and `$ref` cycle protection. A schema that exceeds the depth cap,
> contains a `$ref` cycle, or contains an unresolvable `$ref` is treated as **unconstrained**: the
> tool is classified as though the signal matched, and the finding cites the traversal failure as
> its evidence.

The fail-closed clause is the load-bearing part. A schema too complex or too indirect to traverse
is a schema whose safety cannot be established, and a classifier that shrugs and returns R1 in that
case is defeated by any server willing to nest one level deeper than the parser goes. Depth cap and
cycle protection exist to keep the scanner from hanging, not to create an exemption.

Composition keywords are where real schemas put things. `anyOf` branches in particular are how a
single tool presents two different call shapes, and it is entirely ordinary for only one of them to
carry the dangerous field.

---

## Part 2 — Changes to the Phase 2 brief

### Deliverables — amend item 1

Signal extractors operate over a shared schema-traversal utility in `classify/schema_walk.py`
implementing Rule G. Extractors do not each write their own field matching. The walker yields
(path, property name, subschema) tuples with full JSON-pointer paths, so findings can cite
`input.notification.targets[0].webhook_url` rather than `webhook_url` — the path is the evidence a
reviewer needs to verify the finding by hand.

The walker returns a traversal status alongside its results: `complete`, `depth_exceeded`,
`cycle_detected`, or `unresolvable_ref`. Any status other than `complete` triggers the
unconstrained treatment in Rule G.

### Deliverables — amend item 7

`CHAIN_EXFIL` carries its scope limitation in the finding output itself, not only in the docs. The
finding text states that tools were evaluated and resources were not, so a reader of the report
learns the boundary without consulting the taxonomy.

### Acceptance criteria — add

- A `to` field nested three levels deep inside an `allOf` branch classifies R4, and the finding
  cites the full JSON-pointer path.
- A `$ref` cycle classifies as unconstrained with `cycle_detected` cited, and the scan terminates
  rather than hanging.
- A schema exceeding the depth cap classifies as unconstrained with `depth_exceeded` cited.
- An unresolvable `$ref` classifies as unconstrained with `unresolvable_ref` cited.
- An `if_match` token present only inside a nested object is found by Rule D, proving the walker is
  shared across signal classes rather than reimplemented per rule.
- A tool whose dangerous field appears in only one `anyOf` branch classifies at the higher tier.
- `CHAIN_EXFIL` output states its tools-only scope.

### Fixtures — add to the Amendment 1 matrix

Six schema-traversal fixtures matching the criteria above, in
`tests/fixtures/schema_traversal/`. These are parser fixtures rather than tier fixtures and belong
in their own directory, separate from the tier matrix.

---

## Standing blocker

Pre-work 0 — the rename — still gates this phase. The package name, console script, and every
documentation path move together, and every fixture path written before the rename gets touched
again after it. Do not start Phase 2 implementation until the name is settled.

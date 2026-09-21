# `manifest/` — canonical serialization, hashing, schema

## Responsibility

Turn a raw enumeration capture into a manifest that is **identical for an identical
surface and different for a different one** — on any machine, in any order, at any
time. Define the pydantic models for that manifest, compute its hashes, and read
and write it as JSON.

## Boundary

No network, no subprocess, no MCP SDK. This package is importable by anything, which
is why `diff` and `verify` can operate on files without any transport machinery
being present.

It does not classify risk (`classify/`) — `build_manifest` always produces an
unclassified manifest with `classification: []`; a caller runs
`classify.classify_manifest` on the result to get real tiers. It does not score
injection (`inject/`), and does not render reports (`report/`, Phase 4). Format `2.2` adds
`injection_findings` and `ruleset_version`, both covered by `classification_hash`.

## Layout

| Module | Role |
| --- | --- |
| `raw.py` | `RawSurface` — the contract from `transport` to here: wire JSON, untouched |
| `models.py` | The manifest schema as pydantic models |
| `canonical.py` | Deterministic JSON rendering — the only input to a hash |
| `hashing.py` | The three SHA-256 hash levels |
| `build.py` | `RawSurface` → sorted, hashed `Manifest` |
| `io.py` | Render, parse, load, write |
| `verify.py` | Recompute hashes and report mismatches |

## The hashes

All are required, and AGENTS.md forbids collapsing them.

| Hash | Covers | Answers |
| --- | --- | --- |
| `surface_hash` | tools, resources, prompts, instructions | did anything at all change? |
| `schema_hash` (per tool) | that tool's input schema | did the callable API change? |
| `description_hash` (per tool) | that tool's description text | **did the prompt change?** |
| `capabilities_hash` | the server's declared `capabilities` block | did the protocol-level capability surface change? |
| `classification_hash` | Placard's own `classification` — tiers, citations, reversibility | did *our judgment* of the surface change? |

`capabilities` and `classification` are both outside `surface_hash`'s body — see
"What is deliberately *not* recorded" below for why. `classification_hash` is
computed by `build.compute_classification_hash`, over an empty list for a manifest
`build_manifest` alone produced and over the real entries once
`classify.classify_manifest` has run — either way `build_manifest` itself always
stamps a `classification_hash` matching whatever `classification` it wrote (empty).

The split is the product. A server that rewrites a description while leaving the API
byte-identical has injected new instructions into every agent that connects to it. A
single combined hash makes that indistinguishable from a harmless refactor.

Per-tool hashes are computed before `surface_hash`, so the surface hash covers them
too: editing a schema *and* its recorded `schema_hash` still breaks the surface hash.

Descriptions are hashed through their canonical JSON form rather than raw text, so
an absent description (`null`) and an emptied one (`""`) hash differently. "Removed
the description" and "blanked the description" are different events.

## Determinism rules

1. **Sorted keys.** Dict order reflects how a server happened to serialize a
   response, not a property of the surface.
2. **Stable array ordering.** Tools sort by name, resources by URI, templates by URI
   template, prompts by name — each with the entry's full canonical form as a
   tiebreaker, because the specification does not forbid duplicate names.
3. **Nothing environment-dependent in the body.**

Two renderings exist and never diverge in effect: `canonical_bytes` (compact, the
only thing ever hashed) and `render_json` (indented, what gets written). Changing the
presentation cannot change a hash.

### What is deliberately *not* recorded, or not hashed

- **No timestamp.** A manifest describes a surface, not the moment it was read.
- **No scan target.** The same server reached by two different command lines is the
  same server; recording the path would make manifests machine-specific and break
  the byte-identity guarantee across CI runners.
- **The negotiated protocol version and the SDK version are recorded, but never
  hashed.** Both are properties of the client/server pair for *this scan*, not of the
  surface, and live in the unhashed `environment` block. Recording them (rather than
  omitting them, as Phase 1 originally did) means a reviewer looking at a
  `capabilities_hash` finding has the context to tell "the server changed" from "our
  SDK negotiated differently" without having to guess.

`capabilities` is recorded too, and a server SDK may derive some of its flags
(`listChanged`, `resources.subscribe`) from the negotiated protocol version — so
`capabilities_hash` can still move on a client SDK upgrade with no server-side change
at all. What changed is that this no longer moves `surface_hash`: `capabilities` was
split into its own body with its own hash and its own diff finding
(`server_capabilities_changed`) specifically so that drift is reviewable on its own
terms instead of either masquerading as a tool-surface change or being dropped to
avoid that. Dropping `capabilities` entirely would hide a server that starts or stops
advertising a whole capability class, which is the trade this split avoids having to
make.

**`classification` follows the identical reasoning one layer up.** A tool's tier is
Placard's own judgment about the surface, not a property of the surface itself — a
classifier rule fix (a Rule A regex tweak, a new Rule D evidence idiom) must never
move `surface_hash` for a server that did not change. `tier` therefore does not live
on `ToolEntry` at all; it lives in a separate `ToolClassification` entry under
`Manifest.classification`, hashed independently as `classification_hash`. `diff`
still compares tiers directly (`tier_escalated`), just by reading `classification`
rather than a field on the tool.

## Naming convention in the serialized manifest

- **MCP-owned fields keep their wire spelling**: `inputSchema`, `outputSchema`,
  `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`, `uriTemplate`,
  `mimeType`, `_meta`.
- **Placard-owned fields are `snake_case`**: `manifest_version`, `surface_hash`,
  `capabilities_hash`, `classification_hash`, `environment`, `schema_hash`,
  `description_hash`, `resource_templates`, `tier` (inside a `classification` entry,
  never on the tool itself).

The casing tells a reader who asserted a given field.

## Fidelity

Every model sets `extra="allow"`. A server field this build has never heard of
survives validation, serialization, and hashing intact. Dropping unknown fields would
mean `surface_hash` did not actually cover the surface — the one thing it claims to
do.

## Scope

This package never interprets what it records. Declared annotations
(`ToolAnnotations`) are carried verbatim and are not evaluated here — AGENTS.md
treats server self-declaration as evidence, not truth, and `classify/`'s
declared-vs-inferred reconciliation needs them unmodified. `build_manifest` always
produces `classification: []`; a manifest only carries real tiers once a caller
explicitly runs `classify.classify_manifest` on the result.

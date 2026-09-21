# `diff/` — manifest comparison and escalation rules

## Responsibility

Compare two manifests, produce an ordered list of findings, and resolve them into
the single exit code CI acts on.

## Boundary

Reads manifests. Touches nothing else — no server, no network, no MCP SDK. It does
not re-derive hashes (that is `verify`), does not classify (that is `classify/` —
this package only *reads* the `classification` a manifest already carries), and
does not render (that is `report/`, Phase 4).

It does not print. `cli.py` prints the findings this package returns.

## Exit codes

| Code | Condition |
| --- | --- |
| 0 | No change |
| 1 | Escalation |
| 2 | Description change on an existing tool |
| 3 | Tool removed, or server unreachable |
| 10 | Usage or configuration error |

Codes 3 and 10 also arrive from outside this package: an unreachable server is a
`ConnectionFailure` raised in `transport/`, and a bad invocation is a `UsageError`.

### Combination — a bitmask, not a precedence

When several findings apply at once, the reported status is the **OR of their bits**:
escalation `1`, prompt change `2`, removal `4`, injection `8`. No category masks
another.

The pre-0.3.0 rule was a precedence, `3 > 1 > 2 > 0`, justified by "3 also covers
server unreachable." That justification belonged to `scan` — `diff` reads two files
and never meets a server — and the precedence itself was a ladder that hid
categories: one R0 tool removed plus one R5 egress tool added reported `3`, and a
consumer gating on `1` missed the escalation. Under the bitmask that run reports `5`.

- **2 is never suppressed.** Its bit is set whatever else happened, and the finding
  is always emitted. AGENTS.md: a prompt change is always reviewable and is not
  silenceable by tier configuration.
- **8 is its own bit.** Injection findings almost always arrive alongside a prompt
  change; `2` versus `2 | 8` is the distinction a reviewer needs.

## Re-analysis before comparison (Phase 3 §4)

A side whose recorded `ruleset_version` is not this build's is re-analysed from its
stored surface with the current rules before anything is compared, and the result
says so in `DiffResult.notes`. Without this, every Placard upgrade that improved a
rule produced findings on servers that did not change. Recorded overrides are
re-applied. Injection findings are then paired on `(element, class, excerpt)`, never
on list position, and only a finding with no counterpart on the old side is new.

## Detection (Phase 2 diff narrowing)

| Change | Finding | Code |
| --- | --- | --- |
| Tool present in new, absent in old | `tool_added` | 1 if tier is at/above `--ceiling` (default R4) or unclassified; else 0 |
| Tool present in old, absent in new | `tool_removed` | 3 |
| `schema_hash` differs | `tool_schema_changed` | 1 if unclassified on either side or `--escalate-schema-changes`; else 0 |
| `description_hash` differs | `tool_description_changed` | 2 |
| Tier increased on a tool present in both | `tier_escalated` | 1 |
| `capabilities_hash` differs | `server_capabilities_changed` | 1 — **server-level, no `tool`** |

Three rows are ceiling/config-dependent, resolved in `diff_manifests(..., ceiling=,
escalate_schema_changes=)`:

- **`tool_added`.** Only escalates at or above the configured ceiling. A tool this
  build cannot grade — no `classification` entry on the new side, the Phase 1 shape
  — falls back to the old conservative default: cannot be *shown* to sit below the
  ceiling, so it escalates. AGENTS.md forbids silent downgrades.
- **`tool_schema_changed`.** By default, exit 0 if the tier can be shown not to have
  moved — an increase is caught separately by `tier_escalated`, so this finding does
  not need to double-escalate. `--escalate-schema-changes` reverts to the old
  Phase 1 default (always exit 1) for callers that want it. No classification on
  either side falls back to escalate, the same reasoning as `tool_added`.
- **`server_capabilities_changed`.** A capability delta can be an SDK-derived no-op
  or a server advertising something genuinely new; this build cannot tell those
  apart, so an ungraded delta escalates. `Finding.tool` is `None` for it — it fires
  independently of every tool-level check.

`tier_escalation_findings()` compares tiers read from each manifest's
`classification` (via `Manifest.classification_by_tool()`), not a field on the
tool — see `manifest/models.py`'s note on why classification lives outside
`ToolEntry`. A tool absent from `classification` on either side produces no
`tier_escalated` finding; it cannot be compared, not "assumed unchanged."

## Out of scope

Resource and prompt changes produce no findings — resource/prompt classification is
unimplemented (`docs/TAXONOMY.md`'s `CHAIN_EXFIL` scope note). Instruction changes
also produce no dedicated finding. All three still move `surface_hash`, and
`DiffResult.surface_hash_changed` reports that so the change is not invisible — but
none of it affects the exit code.

## Changing a rule

AGENTS.md: diff rules are tested as a table of (old manifest, new manifest, expected
exit code). **Add the row before changing the rule** — see
`tests/test_diff_table.py`.

# `diff/` — manifest comparison and escalation rules

## Responsibility

Compare two manifests, produce an ordered list of findings, and resolve them into
the single exit code CI acts on.

## Boundary

Reads manifests. Touches nothing else — no server, no network, no MCP SDK. It does
not re-derive hashes (that is `verify`), does not classify (that is `classify/`,
Phase 2), and does not render (that is `report/`, Phase 4).

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

### Precedence

When several findings apply at once, the reported code is `3 > 1 > 2 > 0`.

- **3 outranks everything** because it also covers *server unreachable*. If the scan
  cannot be trusted, nothing derived from it can be either.
- **1 outranks 2** because a capability change outranks a prompt change when both
  are present.
- **2 is never suppressed.** It can be outranked in the returned code, but the
  finding is always emitted. AGENTS.md: a prompt change is always reviewable and is
  not silenceable by tier configuration.

## Phase 1 detection

| Change | Finding | Code |
| --- | --- | --- |
| Tool present in new, absent in old | `tool_added` | 1 |
| Tool present in old, absent in new | `tool_removed` | 3 |
| `schema_hash` differs | `tool_schema_changed` | 1 |
| `description_hash` differs | `tool_description_changed` | 2 |
| Tier increased | `tier_escalated` | 1 — **inert in Phase 1** |
| `capabilities_hash` differs | `server_capabilities_changed` | 1 — **server-level, no `tool`** |

Three Phase 1 mappings are deliberately conservative and all three narrow in a later phase:

- **`tool_added` → 1.** AGENTS.md reserves escalation for a new tool at R4/R5. With
  no classifier, no addition can be *shown* to sit below the ceiling, and AGENTS.md
  forbids silent downgrades. So every addition escalates for now.
- **`tool_schema_changed` → 1.** A schema change can widen blast radius with no other
  signal — a new `force` flag, a `path` that stops being prefix-constrained.
  Ungraded, it escalates.
- **`server_capabilities_changed` → 1.** A capability delta can be an SDK-derived
  no-op or a server advertising something genuinely new. Ungraded, it escalates —
  same reasoning as the two rows above, but note this one says nothing about any
  tool's surface: `Finding.tool` is `None` for it, and it fires independently of
  every tool-level check.

## The tier-escalation stub

`tier_escalation_findings()` is wired into the comparison loop and returns nothing.
Both of its arguments always carry tier `unclassified` in Phase 1, so there is no
ordering to compare — it is inert by construction, not by an early return someone
could delete by accident.

It exists now, rather than being added in Phase 2, so that Phase 2 changes one
function body instead of changing the shape of the diff. `tests/test_diff_tier_stub.py`
asserts the inertness directly, so the day it starts producing findings is the day
that test is rewritten on purpose.

## Out of scope in Phase 1

Resource, prompt, and instruction changes produce no findings. They still move
`surface_hash`, and `DiffResult.surface_hash_changed` reports that so the change is
not invisible — but it does not affect the exit code.

## Changing a rule

AGENTS.md: diff rules are tested as a table of (old manifest, new manifest, expected
exit code). **Add the row before changing the rule** — see
`tests/test_diff_table.py`.

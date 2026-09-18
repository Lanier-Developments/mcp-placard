# Placard

Static analysis and drift detection for the surface an MCP server exposes to an agent.

Teams wire agents to Model Context Protocol servers with no record of what capability they
just granted, and no mechanism to notice when that capability changes. A server can add a
destructive tool, or silently rewrite a tool description — which is a prompt injected directly
into the agent's context — and nothing in the ecosystem today flags either event.

Placard connects to an MCP server, enumerates its surface, emits a canonical hashed
manifest, and fails CI when the next scan disagrees with the last one.

**Placard never invokes a tool.** Enumeration and static analysis only. No code path may
call `tools/call`; `scripts/check_no_tool_invocation.py` enforces that mechanically.

## Status: Phases 1, 2, and 2.1 complete

`scan` classifies every tool on the R0-R5 ladder — schema shape, tool name, description, and
declared-annotation signals combine as a monotonic maximum (never a weighted score), reconciled
against what the server declared about itself. Alongside the tier every tool carries a `kinds`
set (`read_sensitive`, `egress`, `write`, `destructive`, `code_exec`) derived from the same
evidence, and `CHAIN_EXFIL` is a predicate over kinds. The full ladder, its worked examples, and
the rules the classifier implements are in [`docs/TAXONOMY.md`](docs/TAXONOMY.md). `diff` grades
tier increases and gates new-tool escalation on a configurable ceiling; a per-tool
`classification` entry never enters `surface_hash` — a classifier fix must never move that hash
for a server that did not change. Injection heuristics (Phase 3), SARIF/GitHub Action packaging
(Phase 4), and manifest signing (Phase 5) are not yet built.

### Against real servers

Phase 2.1 corrected the classifier against 11 public MCP servers (109 tools) after the first
real-server batch found three compounding rule ambiguities. The before/after, same servers,
same day-old surfaces (every `surface_hash` unchanged — the classifier moved, the servers did
not):

| Server | Tools | Phase 2 | Phase 2.1 | `CHAIN_EXFIL` |
| --- | --- | --- | --- | --- |
| filesystem | 14 | R0:1 R1:1 R2:1 **R5:11** | R0:1 R1:9 R5:4 | spurious → none |
| memory | 9 | R0:1 R1:2 R3:4 R4:2 | R0:1 R1:2 R3:6 | spurious → none |
| github | 26 | R1:15 R3:7 R5:4 | R1:14 R3:10 R5:2 | spurious → none |
| playwright | 26 | R0:3 R1:21 R4:2 | R0:1 R1:7 R3:14 R4:2 **R5:2** | none → `code_exec` |
| git | 12 | R1:11 R2:1 | R1:7 R3:5 | — |
| everything, fetch, time, sequential-thinking, deepwiki, context7 | 22 | unchanged | unchanged | — |

What moved, and why: eight filesystem *reads* left R5 (a `path` on `read_file` is a source, not
a destination); `move_file` reached R5 on `destination`; GitHub's `create_or_update_file` became
R3 `verified` on its `sha`; every git and GitHub mutation verb (`add`, `commit`, `checkout`,
`merge`, `fork`, `reset`) reached R3; the memory server's graph edges (`from`/`to`) stopped
reading as email; Playwright's `browser_evaluate` and `browser_run_code_unsafe` went from R1 to R5
with every kind, and the server's only `CHAIN_EXFIL` is now the one it should have — code
execution carries both halves alone. The full delta and the flag-backs are in
`2026-09-18_from-jr_to-chief_phase2.1-report.md`.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

Requires Python 3.11+. The test suite needs no network access.

## Use

```bash
# Enumerate a server, classify every tool, and print the manifest
placard scan "python -m tests.mock_server"
placard scan https://mcp.example.com/mcp --out manifest.json

# Downgrade a tier only through an explicit, attributable allowlist entry
placard scan "python -m tests.mock_server" --override overrides.json

# Compare two manifests; the exit code is the finding
placard diff baseline.json current.json
placard diff baseline.json current.json --ceiling R5   # only R5 additions escalate

# Confirm a manifest's hashes — including its classification — still describe its own content
placard verify manifest.json
```

`<target>` is a stdio command line or an HTTP(S) URL. The transport is inferred from the target;
`--transport stdio|http` overrides. `--override` points at a JSON array of
`{"entry_id", "tool", "tier", "reason"}` objects — the only way a tier is ever downgraded.
`--ceiling` (default `R4`) sets the tier a new tool must reach before `diff` escalates on it;
`--escalate-schema-changes` reverts to escalating on every input-schema change, even one that
leaves the tier unchanged.

### Exit codes

A per-command contract, pinned in [`AGENTS.md`](AGENTS.md) and in
`tests/test_exit_code_contract.py`. Codes are **categories, not a severity ladder** — `2` is a
different review path from `1`, not a worse outcome than it, and the same number can mean
different things for different commands.

| Code | `scan` | `diff` | `verify` |
| --- | --- | --- | --- |
| 0 | enumerated successfully | no change / below ceiling | every hash matches |
| 1 | — | escalation — new tool at/above ceiling, tier increase, capabilities change | a hash does not match its content |
| 2 | — | description change on an existing tool (always reviewable, never silenceable) | — |
| 3 | server unreachable | tool removed | — |
| 10 | usage/configuration error | usage/configuration error | usage/configuration error |

`diff`'s codes precedence-order as `3 > 1 > 2 > 0` when several apply at once; every finding is
still listed on stderr regardless of which code wins. Codes `20`-`29` are reserved for `report`
(Phase 4, not yet implemented).

## The manifest

Canonical JSON: sorted keys, stable array ordering, nothing environment-dependent in a hashed
body. No timestamp, no scan target — two scans of an unchanged server are byte-identical. The
negotiated protocol version and SDK version *are* recorded, but only inside `environment`, which
no hash ever covers.

Manifest format `2.1`; `2.0` and `1.0` documents still load, verify, and diff — a stored `2.0`
baseline's `classification_hash` reproduces under this build because an empty `kinds` list is
serialized as absent.

Independent SHA-256 hashes, all required, never collapsed:

- `surface_hash` — tools, resources, prompts, instructions
- per-tool `schema_hash` — the input schema only
- per-tool `description_hash` — the description text only
- `capabilities_hash` — the server's declared MCP capabilities block only
- `classification_hash` — Placard's own tier judgment (`classification`) only

Splitting schema from description is what makes *"the server rewrote its prompt but kept the API
identical"* a visible event rather than a silent one. `capabilities` and `classification` are
both split out of `surface_hash` for the same reason in the other direction: some capability
flags are SDK-derived and can drift on a client SDK upgrade, and a classifier rule fix can
change a tier, neither with any server-side change at all — each gets its own finding
(`server_capabilities_changed`, `tier_escalated`) instead of moving `surface_hash`.

## Development

```bash
pytest                          # full suite
pytest -m "not slow"            # skip subprocess integration tests
ruff check . && ruff format --check .
mypy src/
python scripts/check_no_tool_invocation.py
```

Coverage floor is 85% on `src/`, enforced in CI. CI also scans the bundled mock server and
diffs the result against `tests/fixtures/mock_server_manifest.json` — the tool gates itself.

Regenerate that fixture deliberately, never to make a red build green:

```bash
placard scan "python -m tests.mock_server" --out tests/fixtures/mock_server_manifest.json
```

## Documentation

- [`AGENTS.md`](AGENTS.md) — the operating spec
- [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) — what Placard does and does not defend against
- [`docs/TAXONOMY.md`](docs/TAXONOMY.md) — the R0-R5 risk ladder, the kind axis, Rules A-H, worked examples

## License

MIT — see [`LICENSE`](LICENSE). © Lanier Developments.

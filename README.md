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

## Status: Phase 1 complete, Phase 2 in progress

Phase 1 delivers transport, enumeration, the canonical manifest, and `scan` / `diff` / `verify`
with exit codes. **Every tool currently returns tier `unclassified`, by design** — Phase 1
performs no risk classification. If you scan a server and every tool comes back
`unclassified`, that is the scaffold working as intended, not a missing feature. The R0-R5
ladder and its worked examples are specified in [`docs/TAXONOMY.md`](docs/TAXONOMY.md); Phase 2
implements the classifier against them.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

Requires Python 3.11+. The test suite needs no network access.

## Use

```bash
# Enumerate a server and print its manifest
placard scan "python -m tests.mock_server"
placard scan https://mcp.example.com/mcp --out manifest.json

# Compare two manifests; the exit code is the finding
placard diff baseline.json current.json

# Confirm a manifest's hashes still describe its own content
placard verify manifest.json
```

`<target>` is a stdio command line or an HTTP(S) URL. The transport is inferred from the target;
`--transport stdio|http` overrides.

### Exit codes

A per-command contract, pinned in [`AGENTS.md`](AGENTS.md) and in
`tests/test_exit_code_contract.py`. Codes are **categories, not a severity ladder** — `2` is a
different review path from `1`, not a worse outcome than it, and the same number can mean
different things for different commands.

| Code | `scan` | `diff` | `verify` |
| --- | --- | --- | --- |
| 0 | enumerated successfully | no change / below ceiling | every hash matches |
| 1 | — | escalation — new tool, schema change, capabilities change | a hash does not match its content |
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

Independent SHA-256 hashes, all required, never collapsed:

- `surface_hash` — tools, resources, prompts, instructions
- per-tool `schema_hash` — the input schema only
- per-tool `description_hash` — the description text only
- `capabilities_hash` — the server's declared MCP capabilities block only

Splitting schema from description is what makes *"the server rewrote its prompt but kept the API
identical"* a visible event rather than a silent one. `capabilities` is split out of
`surface_hash` for the same reason in the other direction: some capability flags are SDK-derived
and can drift on a client SDK upgrade with no server-side change, so that drift gets its own
`server_capabilities_changed` finding instead of moving `surface_hash`.

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
- [`docs/TAXONOMY.md`](docs/TAXONOMY.md) — the R0-R5 risk ladder with worked examples

## License

MIT — see [`LICENSE`](LICENSE). © Lanier Developments.

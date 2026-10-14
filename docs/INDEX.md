# Blast-radius index

What the agent gains by connecting to each of these widely used public MCP servers, as
Placard classifies it. Every row is a scan of an exact pinned version; the manifests are
committed under [`index/manifests/`](../index/manifests/) and this page is rendered from
them by `scripts/build_index.py`, so anyone can re-run the scan and compare `surface_hash`.

Ruleset **3.6**. Tiers: R0 inert, R1 read-scoped, R2 read-sensitive, R3 write-scoped, R4 egress, R5 irreversible; see
[`TAXONOMY.md`](TAXONOMY.md). Kinds: `read_sensitive`, `egress`, `write`, `destructive`,
`code_exec`. Counts are tools, not risk scores.

| Server | Package | Version | Tools | Tiers | Max | Kinds | `CHAIN_EXFIL` | Injection findings | `surface_hash` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `everything` | `@modelcontextprotocol/server-everything` | 1.0.0 | 13 | R0:6 R1:6 R4:1 | R4 | egress:1 write:1 | no | 0 | `e63a4598744d66da` |
| `filesystem` | `@modelcontextprotocol/server-filesystem` | 1.0.0 | 14 | R0:1 R1:9 R5:4 | R5 | write:4 destructive:3 | no | 0 | `a30f948c10d0f66b` |
| `memory` | `@modelcontextprotocol/server-memory` | 1.0.0 | 9 | R0:1 R1:2 R3:6 | R3 | write:3 destructive:3 | no | 0 | `f5fef51bfc6129b9` |
| `sequential-thinking` | `@modelcontextprotocol/server-sequential-thinking` | 1.0.0 | 1 | R1:1 | R1 | — | no | 0 | `903263dde6ac483a` |
| `playwright` | `@playwright/mcp` | 0.0.83 | 25 | R1:7 R3:14 R4:2 R5:2 | R5 | read_sensitive:2 egress:4 write:6 destructive:18 code_exec:2 | **yes** | 0 | `dfae257aa9523af4` |
| `context7` | `@upstash/context7-mcp` | 4.4.1 | 2 | R1:2 | R1 | — | no | 0 | `45f236e13d93969e` |
| `fetch` | `mcp-server-fetch` | 2026.10.10 | 1 | R4:1 | R4 | egress:1 | no | 0 | `8eb8d5964de9c3c7` |
| `time` | `mcp-server-time` | 2026.10.10 | 2 | R1:2 | R1 | — | no | 0 | `fbb408ee3a5f08cf` |
| `git` | `mcp-server-git` | 2026.10.10 | 12 | R1:7 R3:5 | R3 | write:4 destructive:1 | no | 0 | `6a3c60771ec5f720` |

## Exfiltration chains

- **playwright** exposes a sensitive read and an egress path (4 tools involved): `browser_evaluate`, `browser_navigate`, `browser_run_code_unsafe`, `browser_tabs`.

## How to read this

- **A tier is the worst thing a tool's declared surface lets an agent do**, inferred from its
  schema, name, description and annotations, and reconciled with what the server claims about
  itself. It is a statement about capability, not about whether the server is trustworthy.
- **`CHAIN_EXFIL: yes` means a single server exposes both a sensitive read and an egress**
  path. It is the property worth a second look before connecting that server to an agent that
  also holds credentials.
- **Injection findings are first-sight heuristics with known gaps.** A `0` here does not mean a
  description is safe: on held-out v2 (the published measurement, ruleset 3.3) `override` and
  `concealment` detected 1 of 7 each; ruleset 3.6 addressed the structural misses and its
  generalisation is unmeasured until held-out v3 is scored. See
  [Known limits](INJECTION.md#known-limits).
- **Only the servers' own enumerations are scanned.** No tool was invoked. Servers that need
  credentials or a hosted endpoint (GitHub, DeepWiki) are not in this index.

## Reproducing

```
pip install -e '.[dev]'
python scripts/build_index.py scan      # installs pins in a scratch dir, rewrites the manifests
python scripts/build_index.py check     # fails if this page is not what the manifests render
python scripts/build_index.py reanalyze # after a ruleset change: re-analyse stored surfaces
```

Scanning launches each pinned server as your user. A moved `surface_hash` on an unchanged pin
is a finding in its own right; read the manifest diff before committing it.

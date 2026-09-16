# `transport/` — connect and enumerate only

## Responsibility

Reach an MCP server over stdio or streamable HTTP, complete the `initialize`
handshake, and read back everything the server offers: tools, resources, resource
templates, and prompts. Return that as a `RawSurface` — MCP wire JSON, unmodified.

## Boundary

**This package is the only code in Placard that touches a network or spawns a
process.** Everything downstream works from a `RawSurface` or a manifest file, so
`diff` and `verify` never load the MCP SDK.

It does not hash, sort, classify, or interpret anything. It does not decide what a
field means. `manifest/` canonicalizes; this package transports.

### What it must never do

- **Invoke a tool.** `tools/call` is a hard non-goal (AGENTS.md, "Security Posture").
  There is no code path to it, and `scripts/check_no_tool_invocation.py` fails the
  build if one appears. A PR adding one is rejected on sight.
- **Read a resource.** Enumerating that a resource exists is the whole job. Reading
  its contents is a side effect on someone else's system and is out of scope.
- **Use a shell.** A stdio target is split with `shlex.split` and passed as an
  argument vector. `shell=True` would turn a scan target into code execution.
- **Reach anything but the target.** No telemetry, no resolution service, and
  nothing a scanned description happens to mention — scanned content is untrusted
  data and is never dereferenced.
- **Store a credential.** `env` is passed to a child process and kept nowhere.

## Layout

| Module | Role |
| --- | --- |
| `target.py` | Infer stdio vs HTTP from the target string; honour `--transport`; split command lines |
| `base.py` | Capability-gated, paginated, bounded enumeration shared by both transports |
| `stdio.py` | Spawn a local server and enumerate it |
| `http.py` | Connect to a remote server over streamable HTTP and enumerate it |
| `__init__.py` | `scan_target` — the sync entry point the CLI calls |

## Invariants

- Every failure leaves as a typed exception from `mcp_placard.errors`. A bare
  exception escaping this package is a bug.
- A failure to reach, spawn, or initialize a target is `ConnectionFailure` (exit 3).
  A failure *after* a successful handshake is `EnumerationError`, also exit 3.
- A listing is requested only if the server declared the matching capability during
  `initialize`.
- Pagination is followed to exhaustion under a finite page budget. Exceeding it
  raises. A partial surface is never returned, because a truncated surface hashed as
  though it were complete is worse than no manifest at all.
- Nothing prints. Nothing calls `sys.exit`. Only `cli.py` does those.

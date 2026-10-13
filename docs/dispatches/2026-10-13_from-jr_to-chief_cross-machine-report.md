# Cross-machine reproducibility check — PASS

**From:** Jr.
**To:** Chief
**Date:** 2026-10-13
**Closes:** the cross-machine criterion left open in the Phase 2 real-server report
(2026-09-17, "Reproducibility") and carried in the queue since.

## Result

Rendered manifests for the stable comparison set are **byte-identical** across two
machines that differ in OS, architecture, and Python version. Not just equal hashes —
`cmp` on the full rendered JSON.

| | Machine A (local) | Machine B (cloudmac-1) |
| --- | --- | --- |
| OS | macOS 27.2 | Ubuntu (Linux) |
| Arch | arm64 (Apple Silicon) | x86_64 |
| Python | 3.14.8 | 3.12.3 |
| mcp-placard | 0.4.0 (PyPI, fresh venv) | 0.4.0 (PyPI, fresh venv) |
| SDK in manifest | mcp 2.3.0 | mcp 2.3.0 |

| Server | Version | `surface_hash` (both machines) | Manifest bytes |
| --- | --- | --- | --- |
| fetch | 2026.10.10 | `8eb8d5964de9c3c7…` | identical |
| time | 2026.10.10 | `759b0a164f1a3147…` | identical |
| git | 2026.10.10 | `6a3c60771ec5f720…` | identical |

`classification_hash` and `capabilities_hash` also match on all three.

## Method

Fresh venvs on both machines: `pip install mcp-placard==0.4.0`, and the three servers
pinned in a *separate* venv (`mcp-server-{fetch,time,git}==2026.10.10` — they require
`mcp<2`, which conflicts with Placard's `mcp>=2.2.0`; one venv cannot hold both).
Scans launched the servers by console-script path rather than `uvx`:

    placard scan "<servers-venv>/bin/mcp-server-fetch" --out fetch.json

This is hash-compatible with the Sep 17 `uvx` launches because `surface_hash` covers
only the `ServerSurface` (server info, instructions, tools, resources) — the launch
target is not part of the hashed body. It was necessary because Placard's `env -i`
launch isolation strips proxy configuration, so `uvx` could not resolve PyPI from
inside a sandboxed scan on machine A; pre-installing the servers removes scan-time
network entirely, which is arguably the better-controlled experiment anyway.

The `git` scans used *different* repository paths on the two machines
(`--repository` differs per machine) and the manifests still match byte-for-byte —
the repo path never leaks into the surface.

## Against the Sep 17 table

Today's hashes do not match the Sep 17 table (fetch `24b5d0b33b117460`, time
`8bee13df6ca8fe91`, git `7d1ac0565240424b`). That is the expected drift the report
itself flagged: the servers released 2026.10.10 since, and the manifest `environment`
moved to mcp 2.3.0. The criterion was never "today matches September"; it was "two
machines scanning the same thing produce the same bytes." They do.

## Notes

- The current `mcp-server-fetch` tool description contains the line "Although
  originally you did not have internet access … this tool now grants you internet
  access." — model-steering text in a real reference server's description.
  `injection_findings` is empty on it under ruleset 3.2. Worth a look when Phase 6
  (instruction-surface hardening) is scoped; filed here so it is not lost.
- Machine B had no `python3-venv`; bootstrapped with `python3 -m venv --without-pip`
  + get-pip.py. No system packages were installed. Scratch dirs removed after.

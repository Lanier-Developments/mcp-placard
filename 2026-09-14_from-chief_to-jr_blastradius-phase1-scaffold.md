# Brief: BlastRadius Phase 1 Scaffold

**From:** Chief
**To:** Jr.
**Date:** 2026-09-14
**Repo:** BlastRadius (new — `github.com/Lanier-Developments/BlastRadius`)
**Model:** Opus 5

## Read first

`AGENTS.md` at the repo root is the operating spec. Read it fully before writing code. Two
constraints in it are absolute and are not open to implementation judgment:

1. No code path invokes `tools/call`. Enumeration only.
2. Schema hash and description hash stay separate. Do not collapse them.

## Scope of Phase 1

Stand up the repo and deliver a working `scan` and `diff`. **No classification in this phase** —
every tool lands at `unclassified`. Resist the pull to start inferring risk tiers; that is Phase 2
and it will be written against fixtures that do not exist yet.

### Deliverables

1. **Repo scaffold** — `pyproject.toml` (Python 3.11+, typer, pydantic v2, ruff, mypy, pytest),
   `src/` layout per AGENTS.md, pre-commit config, MIT license, `.github/workflows/ci.yml`
   running lint, types, tests, coverage.

2. **Transport layer** — `transport/stdio.py` and `transport/http.py`. Connect, initialize,
   enumerate tools, resources, and prompts. Transport inferred from target string, `--transport`
   overrides. Connection failures raise typed errors, never bare exceptions.

3. **Manifest** — pydantic models for the server surface. Canonical JSON: sorted keys, stable
   ordering, nothing environment-dependent inside the hashed body. Three SHA-256 hashes:
   `surface_hash`, per-tool `schema_hash`, per-tool `description_hash`. Include a
   `manifest_version` field now so Phase 2 additions do not break old manifests.

4. **`blastradius scan <target>`** — emits manifest JSON to stdout. `--out <path>` writes a file.

5. **`blastradius diff <old> <new>`** — exit codes exactly as the AGENTS.md table specifies.
   Phase 1 handles added tool, removed tool, schema change, description change. Tier escalation
   is stubbed and returns no findings until Phase 2 — leave the branch in place with a test
   asserting it is inert.

6. **`blastradius verify <manifest>`** — recompute hashes, report mismatch.

7. **Mock server** in `tests/mock_server/` exposing a handful of tools with varied schemas and
   annotations, plus one tool whose description can be mutated between runs. This is the fixture
   the whole suite and the self-gating CI job depend on — build it early, not last.

8. **Self-gating CI job** — scan the mock server, diff against a checked-in manifest, fail on
   drift.

### Acceptance criteria

- `pytest` green, coverage ≥ 85% on `src/`, `ruff` and `mypy` clean.
- Scanning the mock server twice with no changes produces byte-identical manifests.
- Mutating only a tool description and re-scanning produces an identical `schema_hash`, a changed
  `description_hash`, and `diff` exit code 2.
- Adding a tool to the mock server produces exit code 1; removing one produces exit code 3.
- `docs/THREAT_MODEL.md` and `docs/TAXONOMY.md` exist with real content. The taxonomy table is
  already specified in AGENTS.md — expand it with two worked examples per tier, since Phase 2
  will be written against those examples.

### Out of scope

Risk classification, injection heuristics, SARIF, signing, GitHub Action packaging, any published
index. Do not scaffold empty modules for them beyond the directories AGENTS.md names.

## Flag back to Chief

- If the MCP Python SDK's enumeration surface does not cleanly expose annotations, stop and report
  rather than working around it — the declared-vs-inferred split in Phase 2 depends on getting
  raw annotation data through Phase 1's manifest intact.
- If canonical serialization proves lossy for any server response field, surface it before
  choosing what to drop.

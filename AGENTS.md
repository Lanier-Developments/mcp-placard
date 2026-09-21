# AGENTS.md — Placard

## Project Overview

Placard is a static analysis tool for Model Context Protocol servers. It connects to an
MCP server, enumerates the surface that server exposes to an agent, classifies the blast
radius of every tool, and emits a canonical, hashed manifest. It then diffs manifests across
versions and fails CI when the blast radius escalates.

The problem it solves: teams connect agents to MCP servers with no record of what capability
they just granted, and no mechanism to notice when that capability changes. A server can add a
destructive tool, or silently rewrite a tool description — which is a prompt injected directly
into the agent's context — and nothing in the ecosystem today flags either event.

Two principles govern every design decision in this repo:

1. **A tool description change is a prompt change.** Descriptions are model-facing input.
   They are hashed separately from schemas and surfaced as reviewable diffs, not metadata noise.
2. **Server self-declaration is evidence, not truth.** MCP annotations (`readOnlyHint`,
   `destructiveHint`, `idempotentHint`, `openWorldHint`) are supplied by the party being
   audited. Placard records declared risk and inferred risk as separate fields and reports
   disagreement as a finding.

**Hard non-goal: Placard never invokes a tool.** It performs enumeration and static
analysis only. No code path may call `tools/call`. A PR that adds one is rejected on sight.

Owner: Lanier Developments. License: MIT. Repo: `github.com/Lanier-Developments/mcp-placard`.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

Requires Python 3.11+. No network access is needed for the test suite; all server interaction
in tests runs against fixtures and a local mock server.

## Commands

| Command | Purpose |
| --- | --- |
| `placard scan <target>` | Connect, enumerate, emit manifest JSON to stdout |
| `placard diff <old.json> <new.json>` | Compare two manifests; exit nonzero on escalation |
| `placard report <manifest.json>` | Human-readable Markdown or SARIF output |
| `placard verify <manifest.json>` | Recompute and check manifest hashes |

`<target>` accepts a stdio command string or an HTTP(S) URL. Transport is inferred; `--transport`
overrides.

Development:

```bash
pytest                    # full suite
pytest -m "not slow"      # fast loop
ruff check . && ruff format --check .
mypy src/
```

## Directory Structure

```
src/mcp_placard/
  cli.py            Command entry points (typer)
  transport/        stdio and http MCP client wrappers — connect and enumerate only
  manifest/         Canonical serialization, hashing, schema (pydantic models)
  classify/         Risk tier inference, declared-vs-inferred reconciliation
  inject/           Injection surface heuristics over every model-facing string (not resource contents)
  diff/             Manifest comparison and escalation rules
  report/           Markdown and SARIF renderers
tests/
  fixtures/         Captured manifests and synthetic server surfaces
  mock_server/      Local MCP server used by integration tests
docs/
  THREAT_MODEL.md   What Placard does and does not defend against
  TAXONOMY.md       Risk tier definitions with worked examples
  INJECTION.md      The seven injection classes, the corpus, the ratchet
  dispatches/       The dated Chief/Jr. briefs, reports, and decisions that produced the rules
```

Every directory under `src/` carries a README.md stating its responsibility and its boundary.

## Risk Taxonomy

Tiers are ordered. A tool receives the highest tier any signal supports.

| Tier | Name | Meaning |
| --- | --- | --- |
| R0 | Inert | No side effects, no data return of consequence — metadata, schema, help |
| R1 | Read-scoped | Reads data inside the server's own declared domain |
| R2 | Read-sensitive | Reads user or organizational data — mail, files, calendar, directory |
| R3 | Write-scoped | Creates or mutates within the server's domain, reversibly |
| R4 | Egress | Moves data outward — send, post, publish, webhook, arbitrary-URL fetch |
| R5 | Irreversible | Delete, purge, revoke, rotate, transfer funds, write credentials |

Inference draws on four signal classes: input schema shape (fields named like `to`, `recipient`,
`url`, `amount`, `path`, `force`), declared annotations, tool name verb, description text. Tier
assignment is a **monotonic maximum over signals; ordering governs citation only** — it never
reduces a tier. `docs/TAXONOMY.md` holds the worked examples and the full rule set (Amendment 1,
Rules A-G); the classifier must cite which signals produced a tier so findings are auditable.

Never silently downgrade a tier because a server declares it safe. Downgrades require an explicit
allowlist entry in the consuming repo's config, and the manifest records that an override applied.
A declaration *against* interest is different: `destructiveHint: true` is a floor of R3 (Amendment
2 §7). Declared values may raise a tier, never lower one.

Alongside its tier every tool carries a `kinds` set — `read_sensitive`, `egress`, `write`,
`destructive`, `code_exec` — derived inside the signal extractors from the same evidence that
produced the tier, never from the tier itself (Amendment 2 §3). Kinds never affect tier and tier
never affects kinds; `CHAIN_EXFIL` is a predicate over kinds. A tool that executes caller-supplied
code is R5 with every kind (Rule H). Every kind, like every tier, must cite the evidence behind it.

## Manifest Format

Manifests are canonical JSON: sorted keys, stable array ordering, no timestamps or
environment-dependent values in the hashed body. Hashing is SHA-256.

Three hash levels, all required:

- `surface_hash` — the whole server surface
- per-tool `schema_hash` — input schema only
- per-tool `description_hash` — description text only

Splitting schema from description is what makes "the server rewrote its prompt but kept the API
identical" a visible event. Do not collapse these into one hash for convenience.

`classification_hash` covers Placard's own analysis — `classification`, `injection_findings`,
and the `ruleset_version` that produced them — and sits outside `surface_hash` so a rule change
never moves the hash of a server that did not change. `diff` re-analyses any side whose
`ruleset_version` is not the current one before comparing (Phase 3 §4): only surface changes can
produce findings. Bump `RULESET_VERSION` on any change to a rule, a field list, a pattern, or a
kind derivation.

## Exit Codes

Exit codes are a **per-command contract** and an interface Phase 4's GitHub Action consumes — a code
changing meaning for a command is a breaking change to that interface, not an implementation detail.
Pin every code for every command in tests; add a row before changing one
(`tests/test_exit_code_contract.py`, `tests/test_diff_table.py`, `tests/test_inject_diff.py`).

Read a code only in the context of the command that produced it. `verify`'s `1` and `diff`'s `1` share
a number, not a meaning.

### `scan`

| Code | Condition |
| --- | --- |
| 0 | Enumerated successfully; manifest written |
| 3 | Server unreachable, or enumeration failed after a successful handshake |
| 64 | Usage or configuration error (unresolvable transport, empty target) |

### `diff` — a bitmask of finding categories

`diff`'s status is the **OR of one bit per finding category** present in the run. Categories are not a
severity ladder and are not ranked: one integer cannot carry several categories exclusively, and any
precedence order masks something (the pre-0.3.0 rule `3 > 1 > 2 > 0` reported `3` for "one R0 tool
removed, one R5 egress tool added," and a consumer gating on `1` missed the escalation). Under the
bitmask a consumer asks `(( rc & 2 ))` for "does this need a prompt review" independent of everything
else in the run.

| Bit | Value | Category |
| --- | --- | --- |
| — | 0 | No findings, or all changes below the configured ceiling |
| 0 | 1 | Escalation — tier increase, new tool at or above `--ceiling` (default R4), capabilities changed |
| 1 | 2 | Prompt change — description changed on an existing element. Never silenceable by tier configuration |
| 2 | 4 | Tool removed |
| 3 | 8 | Injection finding — new in this diff, both sides analysed under the current ruleset |
| — | 64 | Usage or configuration error (unreadable file, malformed JSON, unsupported `manifest_version`). Exclusive: never OR'd with a finding bit, since no comparison happened |

A run with an escalation and a prompt change exits `3`. Every finding is listed on stderr regardless
of the bits. Injection has its own bit rather than joining escalation because the useful signal for a
reviewer is precisely the difference between "the prompt changed" (`2`) and "the prompt changed and it
looks hostile" (`2 | 8`).

A tool absent from a manifest's `classification` — an old `"1.0"` manifest, or one nothing has
classified — falls back to the Phase 1 conservative default (escalate) for both `tool_added` and
`tool_schema_changed`: AGENTS.md forbids treating "we cannot grade this" as "this is safe." A schema
change on a tool that *can* be graded escalates only if it moved the tier (already caught separately
as a tier increase) or if `--escalate-schema-changes` is set.

A change in `kinds` alone is not a diff finding (not yet — see Phase 6).

### `verify`

| Code | Condition |
| --- | --- |
| 0 | Every recorded hash matches its content |
| 1 | At least one recorded hash does not match — the manifest was edited after it was produced |
| 64 | Usage or configuration error (unreadable file, malformed JSON, unsupported `manifest_version`) |

### `report` (reserved, Phase 4)

Not implemented yet. Codes `100`-`109` are reserved for it so nothing in `scan`, `diff`, or `verify`
claims them before Phase 4 defines their meaning, and so the reservation sits clear of any future
fifth finding bit.

### History

0.1.0 and 0.2.0 used exclusive codes with a precedence rule (`3 > 1 > 2 > 0`), usage error `10`, and
`20`-`29` reserved for `report`. 0.3.0 replaced that with the bitmask above in one breaking change;
`10` collides with `8 | 2`, which is why usage error moved.

## Testing

Every risk tier needs fixture coverage in both directions: a tool that belongs in it, and a
near-miss that does not. Classifier changes without a new fixture pair are incomplete.

Diff rules are tested as a table of (old manifest, new manifest, expected exit code). Add a row
before changing the rule.

Injection heuristics are tested against a corpus in `tests/fixtures/injection/` holding both
malicious samples and benign descriptions that superficially resemble them. False-positive rate
on the benign set is a tracked metric, not an afterthought — a scanner that cries wolf gets
turned off. Concretely: the benign half is every model-facing string from the real servers in
`tests/fixtures/real_servers/`, materialised by `scripts/build_benign_corpus.py`; the malicious
half is stored base64-encoded, labelled `synthetic` or `lifted` (with a source), and decoded only
inside test code; `tests/fixtures/injection/baseline.json` is a ratchet CI fails against in
either direction; the annotated hard cases in `benign/hard_cases.json` never flag, with zero
tolerance; and a held-out set under `heldout/` is never opened during development and scored
once with `scripts/score_heldout.py`.

Coverage floor is 85% on `src/`, enforced in CI. Do not lower it to make a PR pass.

## Code Style

Ruff for lint and format, default line length 100. Full type annotations on public functions;
`mypy src/` runs clean in CI. Pydantic models define every serialized structure — no ad-hoc dicts
crossing module boundaries.

Errors are typed exceptions from `mcp_placard.errors`, surfaced by `cli.py` as exit codes. Library
code does not print and does not call `sys.exit`.

## Security Posture

- No `tools/call`. No resource writes. No credential storage.
- Scanned content — tool descriptions, resource text, server names — is untrusted data and is
  never interpolated into a shell command, a file path, or an LLM prompt inside this tool.
- Report renderers escape scanned content. An injection string must not become live markup in the
  Markdown or SARIF output.
- Network egress during a scan goes only to the target server. No telemetry.

## Git and PR Conventions

Branches: `feature/<short-description>`, `fix/<short-description>`.

Conventional commits. One logical change per PR. PR description states what changed, which
fixtures were added, and any exit-code semantics affected.

CI must pass lint, types, tests, and coverage before merge. CI also runs Placard against its
own mock server and diffs the result against a checked-in manifest — the tool gates itself.

## Roadmap

- **Phase 1** — stdio and HTTP transport, enumeration, canonical manifest with three hash levels,
  `scan` and `diff` with exit codes. No classification yet; every tool lands at `unclassified`.
- **Phase 2** — done. Schema walker (Rule G), signal extractors, the Rule F combiner, Rules A-E
  with fixtures, reversibility (Rule D), declared-vs-inferred reconciliation, the override
  allowlist, `CHAIN_EXFIL`, live diff narrowing, and the `manifest_version` bump to `"2.0"` with
  `"1.0"` backward compatibility. `classification` / `classification_hash` sit outside
  `surface_hash`, split out for the same reason `capabilities` was in Pre-work 1: a classifier
  rule fix must never move `surface_hash` for a server that did not change.
- **Phase 2.1** — done. Corrections from the first real-server batch, per Amendment 2: Rule D's
  destination clause (a `path` on a read is a source), Rule C's `to`/`from` exemption, the `kinds`
  axis, `CHAIN_EXFIL` over kinds, Rule H (code execution), the revised reversibility evidence,
  annotation escalation, whole-token verb matching, and `manifest_version` `"2.1"` with `"2.0"`
  baselines still verifying. Real-server fixtures in `tests/fixtures/real_servers/`.
- **Phase 3** — done. Seven deterministic injection classes over every model-facing string
  (`docs/INJECTION.md`), manifest format `2.2` with `injection_findings` and `ruleset_version`,
  re-analysis in `diff` so ruleset changes never produce findings, the bitmask exit contract, a
  benign corpus of 388 real strings with a ratcheted zero false-positive baseline, and an encoded
  malicious corpus with synthetic and lifted provenances reported separately.
- **Phase 4** — GitHub Action wrapper, SARIF output, ceiling configuration.
- **Phase 5** — manifest signing, and a published index of blast radii for widely used public MCP
  servers.
- **Phase 6** (proposed, Amendment 2 §9) — scan a client configuration (`mcp.json`,
  `claude_desktop_config.json`) as a unit and report the blast radius of the *agent*. Across 11
  real servers the true single-server chain count was 0; the nearest real chain was filesystem
  reads plus `fetch` — two servers, one agent. Recorded so it is not lost; not to be built
  speculatively.

Phases ship as separate branches and separate releases. Do not begin a phase before the prior
phase's fixtures are green.

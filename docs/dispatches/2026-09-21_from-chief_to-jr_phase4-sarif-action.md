# Brief: Phase 4 — SARIF, Markdown report, the GitHub Action, and configuration

**From:** Chief
**To:** Jr.
**Date:** 2026-09-21
**Repo:** `Lanier-Developments/mcp-placard`
**Model:** Opus 5
**Release:** 0.4.0
**Precondition:** 0.3.1 (the Phase 3 rulings) merged first. Phase 4 builds on the corrected
`verify`.

## Read first

AGENTS.md, the exit-code section in particular — the bitmask was designed for the consumer this
phase builds, and every design choice below should make that bitmask more useful rather than
paper over it.

## The model this phase implements

Stated once, because everything else follows from it:

> **The committed baseline manifest is the approval record.** A repository checks in one manifest
> per MCP server it depends on. A change in a server's capability surfaces as a diff against that
> baseline. Approving the change means committing the new manifest, which is a pull request, which
> is a code review of exactly what changed. Placard does not need an approval system; the
> repository already has one.

This is why Phase 4 needs no server, no database, and no dashboard. It also means the manifest diff
in a pull request should be readable by a human reviewer, which is a constraint on the Markdown
report.

---

## §1 Configuration — one file

`placard.toml` at the repository root. Pydantic-validated, schema documented, unknown keys an error.

```toml
[defaults]
ceiling = "R4"
baseline_dir = ".placard/baselines"

[[server]]
name = "github"
target = "npx -y @modelcontextprotocol/server-github@2025.4.8"
header_env = ["Authorization=PLACARD_GITHUB_TOKEN"]

[[override]]
server = "github"
tool = "create_pull_request_review"
tier = "R3"
reason = "Review comments reference a file; nothing is written to it."
```

The override allowlist already exists in some form — fold it into this file rather than inventing
a second home for it. One file is the thing a reviewer reads to understand what this repository
has accepted.

Header values are named by environment variable, never written into the file. See §5.

**Pin versions in targets.** `@latest` targets drift under the scanner — you proved that with
Playwright — which is correct behavior for monitoring and wrong behavior for a gate. The config
loader warns on an unpinned `npx`/`uvx` target and documents why.

## §2 `report` — Markdown and SARIF

`placard report <manifest> [--against <baseline>] --format markdown|sarif`

With `--against`, the report covers the diff; without, the full manifest.

### Markdown

For `$GITHUB_STEP_SUMMARY` and for humans. Every scanned string goes through `inject/render.py`
escaping — the step summary renders Markdown, so this is the first place an unescaped excerpt would
become live. Lead with the bitmask decoded into words, then findings grouped by category, then a
per-tool table. A reviewer should be able to approve or reject from the summary alone.

### SARIF 2.1.0

For GitHub code scanning.

- **ruleId**: stable and hierarchical — `placard/escalation/tier_increase`,
  `placard/prompt/description_changed`, `placard/injection/override.<rule>`. The rule catalog is
  emitted in `tool.driver.rules` with help text.
- **message**: `message.text` only. Never `message.markdown`. Every scanned string is escaped
  regardless. SARIF's Markdown field is rendered by GitHub, and a report format that renders
  attacker text is the exact failure the security posture forbids.
- **location**: the committed baseline manifest file as `physicalLocation` — code scanning needs a
  file in the repository to attach an alert to — with a best-effort line region for the element,
  and the JSON Pointer as a `logicalLocation`. If canonical JSON is single-line, line regions are
  meaningless; report that rather than faking them.
- **partialFingerprints**: derived from server name, element pointer, finding class, and excerpt
  hash. This is what lets GitHub track an alert across runs and lets a dismissal persist.
  Without it, every run creates new alerts and dismissals evaporate.

### `level` — the one place a ladder is unavoidable

SARIF's `level` is `error`, `warning`, or `note`, and code scanning uses it for display and
filtering. That is a ladder, and GitHub requires one. Map from category with a configurable table,
defaulting to: injection → `error`, escalation → `error`, prompt change → `warning`,
removal → `note`. Document that `level` is a display hint for code scanning and carries no Placard
semantics. The bitmask remains the contract.

### `report` exit codes

Inside the reserved 100–109. At minimum: 0 rendered, 64 usage, and a code for "the manifest fails
`verify`" — `report` refuses to render a manifest whose hashes do not match, because a report of
tampered data is worse than no report. Propose the rest; do not claim codes outside the range.

## §3 The GitHub Action

A composite action in this repository, `action.yml` at the root.

**Inputs:** `config` (default `placard.toml`), `fail-on` (a list of categories:
`escalation`, `prompt`, `removal`, `injection`; default all but `removal`), `sarif` (upload
toggle, default true), `summary` (step summary toggle, default true).

**Outputs:** `exit-code` (the raw bitmask) and one boolean per category. A downstream step can
route prompt changes to one reviewer group and escalations to another — which is the entire reason
the bitmask exists.

**Behavior:** for each server in the config, scan, diff against the baseline, accumulate the
bitmask across servers by OR, write the summary and SARIF, then fail if any `fail-on` category bit
is set. A server with no baseline yet is reported, not failed — first adoption should not be a red
build.

**Pinning — this one is not negotiable.** The action installs Placard at the version matching the
action's own release tag, with `pip --require-hashes`. A supply-chain security tool whose action
installs whatever PyPI serves today would be a punchline. The README shows consumers pinning the
action by commit SHA, not by tag.

**Dogfood.** Replace the existing self-gate job in this repository's CI with the action itself,
running against the mock server. The tool gated itself from Phase 1; now the action does.

## §4 Baseline workflow

`placard baseline` — scan every configured server and write the manifests to `baseline_dir`.
That is the whole command. It is how a repository adopts Placard and how an approved change gets
committed. It never runs automatically in CI; approving a capability change is a human commit, by
design.

## §5 Threat model additions — scanning executes code

Not in any earlier brief, and the most important section here.

Placard never calls `tools/call`. But scanning a stdio server means **launching** it, and launching
an `npx` package executes that package's code, in the CI runner, with whatever the runner's
environment holds. The guarantee "Placard never invokes a tool" is true and is not the same as
"scanning is safe." A malicious server does not need a tool call to read the runner's environment;
it needs to be started.

Required:

- Each server is launched with an **explicitly constructed environment**: `PATH`, what the
  transport needs, and the headers named for that server in `header_env`. Nothing inherited. A
  server scanned for GitHub never sees the token configured for Slack. Test it — a mock server that
  dumps its environment to a file, asserting only the permitted variables appear.
- `header_env` values never appear in manifests, SARIF, the summary, or stderr. Test with a
  sentinel token value and grep every output.
- The action documents the minimum job permissions — `contents: read`, plus
  `security-events: write` when SARIF upload is on — and recommends running Placard in its own job,
  isolated from deploy credentials.
- `THREAT_MODEL.md` gains a named adversary: the server that attacks the scanner at launch.

HTTP targets do not execute locally, but the same header isolation applies.

## Deliverables

1. `placard.toml` loader, schema, and docs; override allowlist folded in; unpinned-target warning.
2. `report --format markdown` with render-escaped output.
3. `report --format sarif`: rule catalog, text-only messages, physical and logical locations,
   partial fingerprints, configurable `level` mapping.
4. `report` exit codes within 100–109, including the refuse-on-`verify`-failure code.
5. `placard baseline`.
6. `action.yml`: inputs, outputs, OR-accumulated bitmask across servers, `fail-on`, SARIF upload,
   step summary, hash-pinned install.
7. Self-gate CI job replaced by the action.
8. Environment isolation at launch, and header redaction everywhere.
9. THREAT_MODEL.md: the launch-time adversary; AGENTS.md: exit codes for `report`, roadmap updated.

## Acceptance criteria

- SARIF validates against the 2.1.0 schema, and a test uploads nothing but asserts the document
  shape code scanning requires.
- Two runs of an unchanged diff produce identical `partialFingerprints`.
- An injection excerpt containing Markdown and HTML renders inert in both the step summary and the
  SARIF message.
- The env-dump mock server sees only the permitted variables.
- A sentinel header value appears in no output anywhere.
- An action run with a prompt change and `fail-on: escalation,injection` passes, and
  `prompt` output is `true`. That is the routing case, and it is the test that proves the bitmask
  was worth it.
- A server with no baseline is reported and does not fail the build.
- `report` refuses a manifest that fails `verify`.
- Coverage, lint, types, the no-invocation guard, and the injection ratchet all clean.

## Out of scope

Pull-request comments, a hosted service, signing (Phase 5), the public index, the client-config
scan (Phase 6), resource contents.

## Flag back to Chief

- If canonical JSON makes SARIF line regions meaningless, report before choosing between a
  pretty-printed baseline format and accepting file-level locations. Changing how baselines are
  written is a format decision.
- If environment isolation breaks a mainstream stdio server that genuinely needs an inherited
  variable, report the server and the variable rather than widening the inheritance.
- If `--require-hashes` pinning is unworkable inside a composite action, report the constraint
  before choosing a weaker pin.

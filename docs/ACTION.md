# The GitHub Action

Phase 4. The committed baseline manifest is the approval record: a repository checks
in one manifest per MCP server it depends on, a change in a server's capability
surfaces as a diff against that baseline, and approving the change means committing
the new manifest — a pull request, which is a code review of exactly what changed.
Placard does not need an approval system; the repository already has one.

## Adopt

```bash
pip install mcp-placard
cat > placard.toml <<'EOF'
[[server]]
name = "github"
target = "npx -y @modelcontextprotocol/server-github@2025.4.8"
env = ["GITHUB_PERSONAL_ACCESS_TOKEN"]
EOF
placard baseline          # scans every configured server, writes .placard/baselines/<name>.json
git add placard.toml .placard && git commit -m "Adopt Placard: baseline the GitHub MCP server"
```

`placard baseline` is how a repository adopts Placard and how an approved change is
committed. It never runs in CI. Approving a capability change is a human commit, by
design.

## Gate

```yaml
# .github/workflows/placard.yml
name: Placard
on: [pull_request, push]
jobs:
  placard:
    runs-on: ubuntu-latest
    # A dedicated job: scanning launches each configured server's code as this
    # runner's user. Give it nothing it could steal — no deploy credentials, no
    # checkout of secrets, only the permissions below.
    permissions:
      contents: read
      security-events: write   # only if sarif: true
    steps:
      - uses: actions/checkout@v5
      - uses: Lanier-Developments/mcp-placard@<commit-sha>   # pin by SHA, not by tag
        id: placard
        with:
          fail-on: escalation,prompt,injection,incomplete
        env:
          GITHUB_PERSONAL_ACCESS_TOKEN: ${{ secrets.MCP_GITHUB_TOKEN }}
```

**Pin the action by commit SHA.** A tag can be moved; a SHA cannot. A supply-chain
security tool whose consumers pin it by a movable tag would be a punchline, and so
would one whose action installed whatever PyPI served today — so the action installs
every dependency (the build backend included) hash-pinned from
`requirements/action.txt`, and Placard itself from its own checkout at the SHA you
pinned, with build isolation off. PyPI is never trusted for Placard.

### Inputs

| Input | Default | Meaning |
| --- | --- | --- |
| `config` | `placard.toml` | The configuration file |
| `fail-on` | `escalation,prompt,injection,incomplete` | Categories that fail the job. `removal` is off by default: a tool going away shrinks the blast radius |
| `sarif` | `true` | Upload the SARIF log to code scanning (needs `security-events: write`) |
| `summary` | `true` | Write the Markdown report to the step summary |
| `python-version` | `3.12` | Python to run Placard with |

### Outputs — the reason the bitmask exists

| Output | Meaning |
| --- | --- |
| `exit-code` | The raw bitmask: 1 escalation, 2 prompt change, 4 removal, 8 injection, 16 incomplete |
| `escalation`, `prompt`, `removal`, `injection`, `incomplete` | `true` when that bit is set |

A downstream step can route a prompt change to one reviewer group and an escalation
to another:

```yaml
      - if: steps.placard.outputs.prompt == 'true'
        run: gh pr edit "$PR" --add-reviewer prompt-reviewers
      - if: steps.placard.outputs.escalation == 'true'
        run: gh pr edit "$PR" --add-reviewer security
```

### Behaviour

For each server in the config: scan it in an isolated environment, diff against its
baseline, accumulate the bitmask across servers by OR, write the summary and the
SARIF log, then fail if any `fail-on` category bit is set. A server with **no
baseline yet is reported, not failed** — first adoption is not a red build. A server
that **cannot be scanned sets bit 16** and fails by default: a gate that passes on a
server it never looked at is fail-open.

## What scanning executes

Placard never calls `tools/call`. But scanning a stdio server means **launching**
it, and launching an `npx` package executes that package's code, as the runner's
user. So every launch gets an explicitly constructed environment: `PATH`, a fresh
temporary `HOME` per launch (the secrets in a real home are files — `~/.npmrc`,
`~/.docker/config.json`, credential helpers), redirected package caches, and only the
variables named in that server's `env`. A server scanned for GitHub never sees the
token configured for Slack. HTTP targets get only the headers named in their
`header_env`. No credential value ever reaches a manifest, a report, an output, or
stderr.

**This is not a sandbox.** The launched process still runs as the runner's user with
the runner's filesystem access. Run Placard in its own job, with no deploy
credentials and no checkout of secrets, because the code it launches is the code you
are auditing. `docs/THREAT_MODEL.md`, adversary A7.

## Pin your targets

`@latest` targets drift under the scanner — the Playwright package shipped a release
between two runs of the reference batch and the diff caught it. That is correct for
monitoring and wrong for a gate: a gate should compare the same server version the
baseline was approved for. `placard check` warns on an unpinned `npx` or `uvx`
target.

## Elsewhere than GitHub

`placard check --config placard.toml --sarif out.sarif --summary out.md --outputs out.json`
does everything the action does. Its exit status is the bitmask; `out.json` carries
the per-category booleans and the `fail` decision for the `--fail-on` you passed. Any
CI can gate on that.

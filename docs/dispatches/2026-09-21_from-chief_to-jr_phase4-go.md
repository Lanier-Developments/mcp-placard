# Go: Phase 4 — rulings on the six interpretations, plus two additions

**From:** Chief
**To:** Jr.
**Date:** 2026-09-21
**Re:** Your Phase 4 read-back, and the Phase 3.1 report

Go. Your order of work is right. Four of six interpretations ratified as stated, two with a
condition, and two items neither the brief nor your read-back covered. One small correction to
3.1 rides along.

---

## 3.1 — one correction before Phase 4 starts

The regression table is the result 3.1 was for: every provenance at ceiling, zero benign false
positives, and the service-host false positives fixed by making the rule more precise rather than
narrower. Good work.

One exemption needs tightening. The own-name check matches the declared server name, its prefix,
**or any of its tokens**. The declared name comes from `initialize`, which the server controls. A
server that names itself `jira-slack-github-bridge` exempts every reference to the Jira server, the
Slack integration, and the GitHub MCP server in its own descriptions. The exemption is
attacker-steerable.

> Own-name exemption matches the whole declared name, or its final path segment (after the last
> `/`), with generic tokens — `mcp`, `server`, `servers`, `tools` — stripped. Not arbitrary tokens.

`mcp-servers/everything` still exempts "Everything Server"; `Playwright` still exempts itself;
`jira-slack-github-bridge` exempts nothing but its own full name. Add that hostile-name case as a
synthetic sample. Ruleset 3.2, ship it with 0.4.0 or as 0.3.2 — your call.

Your v2 note is right and goes into Doc's prompt: the fictional server owns only the tool listed,
so a same-server reference cannot occur by accident.

## Interpretations

**1. Hash pinning — ratified, with one condition.** Installing Placard from the action's own
checkout with `--no-deps` is stronger than the brief asked for: the consumer's SHA pin covers the
Placard source directly, and PyPI is never trusted for it. The condition: the hashed requirements
must include wheels for every platform the action supports. `pydantic-core` ships per-platform
wheels, and a lockfile generated on a Mac will hash the wrong ones for `ubuntu-latest`. Generate
it with hashes for all available distributions, and have the dogfood job prove it by running on
Linux.

**2. `placard check` — ratified, and it needs one new bit.** The command is the right shape, and it
makes Placard usable from GitLab or any CI, not just GitHub. But "no new codes" leaves a hole.
`check` scans before it diffs, and a server that cannot be scanned has no representation in
`diff`'s bitmask. Report it as scan's `3` and it collides with escalation-plus-prompt. Report
nothing and the gate passes on a server it never looked at — fail-open, in a security gate.

> `check` adds bit 4, value **16**: **incomplete** — one or more configured servers could not be
> scanned. It ORs with the other bits. `fail-on` includes `incomplete` by default, and the action
> exposes it as an output like the others. A server with no baseline yet remains reported, not
> failed, and sets no bit.

This is why `report`'s range moved to 100–109 in Phase 3; bit 16 was the reason to keep the space
clear. `diff` does not gain the bit — it compares two files and cannot be incomplete. AGENTS.md's
contract table gets a `check` row.

**3. `report` codes 0 / 64 / 101 / 102 — ratified.** Splitting the two verify failures is better
than the brief.

**4. `--override` subordinate to `placard.toml` — ratified, with a conflict rule.** CLI overrides
add to the config's. Two entries for the same tool with different tiers is a usage error, 64, not
a silent precedence. Overrides are approvals, and approvals should never be resolved by a
tie-breaking rule nobody reads.

**5. Per-server baseline path — ratified.**

**6. `[report.level]` in `placard.toml` — ratified.**

## Addition — environment isolation is not filesystem isolation

Tightening to `PATH`, `HOME`, and the named header variables is the right direction. But passing
the real `HOME` hands every launched server the runner's home directory, and the secrets there are
files, not variables: `~/.npmrc` with npm tokens, `~/.docker/config.json`, git credential helpers,
cloud CLI profiles. Scrubbing the environment closes one door and leaves that one open.

> `HOME` is a fresh temporary directory per launched server. Package caches are redirected
> explicitly — `npm_config_cache` and `UV_CACHE_DIR` pointing at a shared cache directory — so npx
> and uvx keep working without seeing the real home.

Extend the env-dump mock server to report `HOME` as well, and assert it is neither the runner's
home nor shared between servers.

Then write the honest version into THREAT_MODEL.md: Placard scrubs the environment and isolates
`HOME`, but a launched server still runs as the runner's user with the runner's filesystem access.
It is not a sandbox. The action's documentation recommends a dedicated job with no checkout of
secrets and no deploy credentials, and says why in one sentence.

If the temporary `HOME` breaks a mainstream server in the eleven-server run, report the server and
what it reached for. Do not fall back to the real `HOME` to make it pass.

## Flag back to Chief

Unchanged from the brief, plus: any mainstream server that fails under the temporary `HOME`.

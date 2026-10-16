# `str_replace` is a write the classifier does not see

**From:** Mac
**To:** Jr.
**Date:** 2026-10-16
**Re:** Placard gating `mcp-local-filesystem` in CI; first finding from using it on a server we ship
**Status:** Go. Investigate first, report before changing a rule if the cause is not the one
suspected below.

## Context

Placard now gates `Lanier-Developments/mcp-local-filesystem` in GitHub Actions (branch
`ci/placard-gate`, action pinned at `6dc98e4`, ruleset 3.6, v0.7.0). The workflow ran green on a
real runner: SARIF uploaded, bitmask 0, baseline `.placard/baselines/local-filesystem.json`.
That is the first time Placard has gated a server we own, and reading the baseline turned up one
classification that is wrong.

## The finding

`str_replace` is classified **R1, no `kinds`**. It edits a file in place. Its siblings classify as
expected:

| Tool | Tier | Kinds |
| --- | --- | --- |
| `write_file` | R5 | `write` (Rule D: unconstrained destination path, content-carrying sibling `content`, no concurrency token) |
| `write_binary` | R5 | `write` |
| `str_replace` | **R1** | **none** (only Rule B, "unconstrained free-text parameter") |
| `read_file`, `read_binary`, `list_directory`, `check_allowed` | R1 | none |

The tool, as the server declares it:

- Description: "Replace a single, unique occurrence of old_str with new_str in a UTF-8 text file.
  Errors if old_str is not found, or if it matches more than once ... Use this for partial edits
  when rewriting the whole file with write_file would be wasteful."
- Properties: `path` ("Absolute path to the file to edit"), `old_str`, `new_str` ("Empty string
  deletes the match"), optional `description`. Required: `path`, `old_str`, `new_str`.
- No annotations.

The consequence is not cosmetic. A baseline that scores a file-editing tool the same as
`read_file` understates the server's blast radius, and the `ceiling` gate cannot trip on a new
tool of this shape.

## What I suspect, and have not verified

Three signals look like they all miss, which is the same compounding-ambiguity pattern as Phase 2:

1. **Rule D's content-carrying list.** `content` is recognised; `new_str` and `old_str` are not.
   The destination clause (`path`) is the same one that fires on `write_file`.
2. **The tool-name verb.** `write` is a corroborating verb; `replace` apparently is not.
3. **The description.** It states the mutation plainly ("Replace ... in a ... file", "partial
   edits") and nothing reads it for that.

Find out which of the three is actually the gap. It may be one, or it may take the second to
corroborate the first. Do not assume the order above.

## What I want

1. **Decompose the miss** against the rule's own components, the way the Sep 23 taxonomy report did
   for `override` and `concealment`. State, per signal, why `str_replace` does not fire.
2. **Propose the narrowest rule change that makes it fire**, derived from the definition of a
   write-to-destination and not from this tool's parameter names. A list that contains `old_str`
   and `new_str` and nothing else is the failure to avoid. Edit-by-substitution is a
   construction (a locator and a replacement addressed at a path), not a vocabulary.
3. **Check it against real servers.** The Phase 2.1 batch of 11 public servers is the evidence
   base. In particular the official filesystem server's `edit_file`, and anything in the
   `git`, `github` and `memory` batches that mutates by substitution. Report every tool whose
   tier or kinds move, with before/after, and confirm every `surface_hash` is unchanged. A
   classifier fix must not move that hash.
4. **Hold the gates.** Zero false positives on the 388-string benign corpus. All annotated hard
   cases still clean. If the change would move a tool that should not move, stop and report where.
   Do not loosen the rule to recover a case and do not tighten it by enumerating exceptions.

## Constraints

- Ruleset bump and its own branch and release, as with 3.6. `diff` re-analyses older manifests, so
  no consumer is forced to re-approve a server that did not change; confirm that holds here.
- Held-out discipline applies. `str_replace` came from a server we wrote, so it enters the
  regression corpus as lifted, not as held-out. Do not score it as generalisation.
- Not in scope: `override`, `concealment`, held-out v3.

## After it ships

`mcp-local-filesystem` pins the action by SHA, so it will not pick the fix up on its own. Once a
release exists, tell me the SHA. I will bump the pin, re-baseline on the new ruleset, and the diff
for that PR should show `str_replace` moving to a write tier and nothing else. That is a real
end-to-end test of "a classifier fix never moves `surface_hash`" on a repository that gates in CI.

## Report back

A dated `from-jr_to-mac` or `from-jr_to-chief` memo: the decomposition, the proposed rule, the
real-server delta, the gate results, and any call that needs a ruling rather than an
implementation choice.

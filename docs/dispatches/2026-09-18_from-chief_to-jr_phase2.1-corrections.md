# Brief: mcp-placard Phase 2.1 — Classifier corrections

**From:** Chief
**To:** Jr.
**Date:** 2026-09-18
**Re:** Your Phase 2 real-server report of 2026-09-17, commit `e5545e0`
**Repo:** `Lanier-Developments/mcp-placard`
**Model:** Opus 5

## Read first

`TAXONOMY-amendment-2.md`. Every decision below is specified there; this brief is the work order,
not the specification. Fold Amendment 2 into `docs/TAXONOMY.md` as the first task, same as Amendment
1.

The report did its job. All four flag-backs were real, three of them compounding, and you stopped
at each one instead of tuning. Two of the items you filed under "gaps, not ambiguities" turned out
to matter more than two of the ambiguities — the `destructiveHint` observation and the code-execution
miss are both in Amendment 2 as rule changes.

## Scope

Correct the classifier against Amendment 2. No new phase capability. Injection heuristics remain
Phase 3.

## Deliverables

**1. Rule D destination clause** — replace the `DESTINATION_PATH_FIELDS = {"path"}` match with the
three-condition test in Amendment 2 §1. Add the destination-named field list. Expected effect on
the reference filesystem server: the eight reads drop from R5 to R1/R2, their `readOnlyHint`
disagreements disappear, and `move_file` rises to R5 on `destination`.

**2. Rule C `to` exemption** — Amendment 2 §2. Sibling `from` plus no content-carrying sibling.
Applies to `to` only.

**3. Kind axis** — Amendment 2 §3. `kinds` is a set on every tool, derived from the same evidence
objects the tier came from, so a kind is never assigned without a citation. This is a manifest
format change: bump `manifest_version` and keep the Phase 2 compatibility fixture green.

Derive kinds inside the signal extractors, where the evidence already lives. Do not add a second
pass that re-inspects the schema to guess kinds — that reintroduces exactly the drift the shared
walker was built to prevent.

**4. `CHAIN_EXFIL` over kinds** — Amendment 2 §4. Delete `READ_HALF_TIERS` and `EGRESS_HALF_TIERS`.
The finding keeps its tools-only scope statement in the output.

**5. Rule H, code execution** — Amendment 2 §5. New signal module. Note the deliberate fail-open on
an ambiguous `query` parameter; this is the single exception to fail-closed in the taxonomy and it
needs a comment in the code saying so, or someone will "fix" it.

**6. Reversibility list** — Amendment 2 §6. Add `sha`-with-content-sibling to `verified`. Remove
`idempotentHint` as the `asserted` source and replace it with the description-evidence list. Expect
`unverifiable` to become the common value; that is the intended outcome, not a regression.

**7. Annotations may escalate** — Amendment 2 §7. `destructiveHint: true` sets kind `destructive`
and a floor of R3. Confirm the disagreement-finding logic still only fires on declared-safer-than-
inferred, not on declared-more-dangerous.

**8. Verb matching defect** — this is a bug, not a gap. The prefix match means `git_add` never
matches `add_`, so every namespaced mutation verb escapes. Match verb tokens anywhere in the
split name, snake and camel. While in there, extend the lists with the verbs the report found
missing: `merge`, `push`, `reset`, `checkout`, `commit`, `fork`, `move`, `rename`.

**9. Sensitivity vocabulary** — remove `directory`. Amendment 2 §8.

## Acceptance criteria

Regression suite — all of these are drawn from real surfaces in your report, so capture them as
fixtures from the actual server schemas rather than hand-written approximations:

- Filesystem server: `read_file`, `list_directory`, `get_file_info` and the other five reads
  classify R1/R2 with no `readOnlyHint` disagreement. `move_file` classifies R5 on `destination`.
- Filesystem server raises no `CHAIN_EXFIL`, or raises one whose halves are both real.
- Memory server: `create_relations` and `delete_relations` are not R4, and raise no `openWorldHint`
  disagreement.
- GitHub server: `create_or_update_file` reaches `verified` on `sha` with its content sibling.
  `merge_pull_request`, `fork_repository` and the git mutation verbs classify at R3 or above.
- Playwright: `browser_run_code_unsafe` and `browser_evaluate` classify R5 with kind `code_exec`
  and carry all four other kinds. The server raises `CHAIN_EXFIL` on that basis alone.
- A search tool with an ambiguous `query` parameter does **not** receive `code_exec`.
- `git_reset` and `move_file` classify at R3 or above on their own `destructiveHint: true`.
- Memory `delete_entities` no longer reaches `asserted`.
- Every kind assignment carries a citation; one global test asserts this across all fixtures, same
  shape as the existing tier-citation test.
- Coverage floor 85%, lint, types, and the no-invocation AST guard all clean.

Then rerun the full 11-server batch and report the new tier and kind distribution against the old
one. The delta table is the artifact — it shows the corrections landed and gives us a before/after
that is worth keeping for the README.

## Still open from Phase 2

- **Cross-machine reproducibility.** Needs the second machine. Your surface-hash table is the
  comparison set; `fetch`, `time`, `git`, and the pinned reference servers are the stable subset.
  The remote HTTP and `@latest` targets are expected to drift and a mismatch there is not a bug.
- **Slack.** Worth rescanning with a real token if one becomes available — the batch has no
  authenticated R4 sample, and `slack_post_message` with `channel_id` is the canonical Rule C case.

## Out of scope

Injection heuristics, SARIF, GitHub Action packaging, signing, the public index, resource and
prompt classification, additional chain types, and the multi-server config scan in Amendment 2 §9.
That last one is Phase 6 and is recorded so it is not lost — do not start it.

## Flag back to Chief

- If the Rule D three-condition test still leaves a real read at R5, or still lets a real write
  escape, stop and report with the schema.
- If `code_exec`'s `query` discriminator proves unworkable against real descriptions, report rather
  than widening it. Widening that signal is how every search tool in the ecosystem becomes R5.
- If removing `idempotentHint` leaves `asserted` empty across all 11 servers, say so. A state that
  never occurs is a state worth deleting, and that is a taxonomy decision rather than yours or mine
  to make silently.

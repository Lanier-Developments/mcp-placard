# Report: Phase 2 classifier against real MCP servers

**From:** Jr.
**To:** Chief
**Date:** 2026-09-17
**Re:** The four "flag back to Chief" items in the Phase 2 brief (rev 2), plus the
cross-machine reproducibility criterion.
**Placard commit:** `e5545e0` on `main`.

## Summary

Scanned 14 public MCP servers. 11 enumerated; 3 refused to start for reasons outside
Placard (missing real credentials, no browser). 109 tools classified. Every tool carries
at least one citation. Zero traversal failures. Rescans are byte-identical.

The headline is **question 1**: three rules are ambiguous against real surfaces, and the
ambiguities compound. Rule D's destination-path clause puts every path-taking *read* at R5.
Rule C's `to` fires on graph edges. `CHAIN_EXFIL` buckets by tier rather than by read/egress
kind. The result is that all three `CHAIN_EXFIL` findings are spurious and 8 of 14 filesystem
read tools are R5. Nothing was tuned; per the brief, these are for you to decide.

Per-server results, hashes, and the raw manifests are at the end.

---

## Q1 — Rules A through G against real surfaces

### D-1. Rule D's "destination path parameter" has no direction

Rule D says a "destination path parameter with no concurrency token present" forces R5.
`schema_shape.py` implements this as `DESTINATION_PATH_FIELDS = {"path"}`: any string
`path`, anywhere in the schema, is R5. The schema alone cannot say whether `path` is a
source or a destination.

On the reference filesystem server, 11 of 14 tools land at R5. Eight are reads:

| Tool | Declared | Inferred | Why |
| --- | --- | --- | --- |
| `read_file`, `read_text_file`, `read_media_file` | `readOnlyHint: true` | R5 | `path` |
| `list_directory`, `list_directory_with_sizes`, `directory_tree` | `readOnlyHint: true` | R5 | `path` |
| `get_file_info`, `search_files` | `readOnlyHint: true` | R5 | `path` |

Each raises a `readOnlyHint` disagreement, so the report reads as "the server lies about
eight tools," which it does not. GitHub's `get_file_contents` lands at R5 the same way.

This is exactly the outcome Rule D's own rationale rejects: "default all overwrites to R5
... would place most of the write surface of most servers into the top tier, fire the CI
gate continuously, and end with somebody turning the gate off." Here it is most of the
*read* surface.

Two readings of the rule, both defensible:

- **Fail-closed (current).** A path is a path. The tool name and `readOnlyHint` are
  server-supplied and cannot be trusted to establish direction. Cost: the filesystem
  server, the most common MCP server in existence, is unusable under any ceiling below R5.
- **Conditional.** The R5-forcing path clause applies only once some independent signal
  already places the tool at R3 or above (write/destructive verb, `destructiveHint: true`,
  or a content-carrying sibling field such as `content`, `body`, `data`, `edits`). A read
  with `path` stays at R1/R2 by Rule B. The verb is server-supplied too, so a tool named
  `get_file` that actually writes would evade R5, but it still lands at R1+, its schema and
  description are still hashed, and this is no worse than any other verb-based signal.

I recommend the conditional reading, but the brief says stop and report. Your call.

### C-1. Rule C's `to` collides with edge and range semantics

Memory server, `create_relations` and `delete_relations`: the schema is
`relations[].{from, to, relationType}`. Rule C fires R4 on
`/properties/relations/items/properties/to` and raises an `openWorldHint: false`
disagreement. The field is a graph-edge endpoint, not a recipient.

The `from`/`to` pair is a common idiom for edges and ranges (`date_from`/`date_to`,
`from`/`to` on a diff, an interval, a transfer between two internal accounts). Rule C
as written has no exception. A narrow refinement would be: `to` with a sibling `from`
in the same object is an edge or range, not a communication target. I did not apply it.

### CHAIN-1. `CHAIN_EXFIL` halves are tier buckets, not read/egress kinds

The taxonomy defines the chain as "at least one R2-or-above read and at least one R4
egress." The tier ladder has no separate read/write axis, so `chain.py` had to express
"read" and "egress" as tier sets: `READ_HALF_TIERS = {R2, R3}` and
`EGRESS_HALF_TIERS = {R4, R5}`. But R3 is write-scoped and R5 is irreversible. Neither is
a read, and R5 is not egress.

Every `CHAIN_EXFIL` raised in this batch is spurious as a result:

| Server | "Read" half as reported | "Egress" half as reported |
| --- | --- | --- |
| filesystem | `move_file` (an R2 by description text) | 11 tools, 8 of them reads mis-tiered to R5 by D-1 |
| github | `add_issue_comment`, `create_branch`, `create_issue`, ... (R3 writes) | `get_file_contents`, `push_files`, ... (R5 by D-1) |
| memory | `add_observations`, `create_entities`, `delete_*` (R3 writes) | `create_relations`, `delete_relations` (R4 by C-1) |

True read-plus-egress chains found: **0 of 11**. The nearest real chain in the batch
is cross-server (filesystem reads plus `fetch`), which is out of scope.

Fixing this needs either (a) a per-tool *kind* alongside the tier, derived from which
signal produced it (Rule A/C evidence means egress; sensitivity-field or description
evidence means read), or (b) narrowing to exactly-R2 reads and exactly-R4 egress. Option
(a) is more honest. Both are taxonomy changes.

### Gaps, not ambiguities

These are cases where a rule is unambiguous and simply has no coverage. Listed for the
record, not for tuning now.

- **Verb list misses common mutation verbs.** `merge_pull_request` (R1),
  `fork_repository` (R1), `git_commit`, `git_checkout`, `git_add`, `git_reset` (all R1).
  `WRITE_VERBS` and `DESTRUCTIVE_VERBS` cover `write_`, `create_`, `update_`, `set_`,
  `add_`, `put_`, `delete_`, `purge_`, `remove_`. Not `merge`, `push`, `reset`, `checkout`,
  `commit`, `fork`, `move`, `rename`. Also the prefix match assumes `verb_` at the start,
  so `git_add` never matches `add_`.
- **`destructiveHint: true` is never an escalating signal.** `git_reset` and `move_file`
  both *declare* `destructiveHint: true` and land at R1 and R2. The annotations signal only
  raises disagreements when the server declares something safer than we inferred. A
  server that declares *more* danger than we can infer is currently ignored. AGENTS.md
  says declared values never *reduce* a tier; it does not say they cannot raise one.
- **`destination` is not in the path list.** `move_file(source, destination)` is the
  clearest overwrite on the filesystem server and lands at R2 because Rule D keys on
  `path` alone. `DESTINATION_PATH_FIELDS` should plausibly include `destination`,
  `dest`, `target_path`, `output_path`. Note this interacts with D-1: if the conditional
  reading is adopted, `destination` is a stronger direction signal than `path`.
- **Arbitrary code execution has no tier.** `browser_run_code_unsafe` and
  `browser_evaluate` on Playwright land at R1. Nothing in the ladder covers "runs
  caller-supplied code." Probably a Phase 3 or taxonomy question.
- **`directory` as a sensitive-domain word.** The description signal treats "directory"
  as R2 (meaning a user directory, per the `list_directory_users` example). On the git
  and filesystem servers it means a folder. `move_file` and `git_diff_unstaged` are R2
  for this reason alone.

## Q2 — Reversibility evidence list

**0 of 26 tools at R3 or above reached `verified`.** 22 `unverifiable`, 4 `asserted`.

Concurrency idioms present in the batch that the list does not recognise:

- **`sha` on GitHub `create_or_update_file`.** Described as "SHA of the file being
  replaced (required when updating existing files)." This is the GitHub Contents API's
  optimistic-concurrency token, exactly the kind of "equivalent" Rule D's list gestures
  at. It should count. Caution: `sha` is also a plain commit reference on read tools, so
  it is only evidence of a *guarded write* when a content-carrying sibling is present.
- **`dryRun` on filesystem `edit_file`.** A preview flag, not a concurrency token, but it
  is schema evidence that the write is guarded. Whether it belongs under `verified` or a
  fourth state is a taxonomy question.
- **`commitId` on `create_pull_request_review`.** Pins the review to a commit. Weak; noted
  only for completeness.

One observation on `asserted`: it is populated solely from `idempotentHint: true`. Memory's
`delete_entities` and `delete_observations` are `asserted` on that basis. An idempotent
delete is not a reversible one. `idempotentHint` may be the wrong proxy for "the server
implies reversibility."

## Q3 — `CHAIN_EXFIL` fire rate

Fired on 3 of 11 servers (27%). Not "most." But all three are false positives caused by
D-1, C-1, and CHAIN-1 above, and the true rate is 0 of 11. This is neither an ecosystem
finding nor a tuning problem. It is a definition problem, and it resolves when Q1 does.

## Q4 — Depth cap

**0 traversal failures across 109 tools.** No `depth_exceeded`, `cycle_detected`, or
`unresolvable_ref` on any real schema. The walker correctly cited nested paths on the
schemas that had them:

- GitHub `create_pull_request_review`: `/properties/comments/items/anyOf/0/properties/path`
- GitHub `push_files`: `/properties/files/items/properties/path`
- Memory `create_relations`: `/properties/relations/items/properties/to`

The `anyOf` case is the one the addendum singled out, and it worked on a real schema.
No reason to relax the cap.

## Reproducibility

Three servers rescanned on this machine: `deepwiki-http`, `fetch`, `filesystem`. All
three manifests byte-identical to the first scan. The **cross-machine** criterion is still
open; it needs the second machine. Surface hashes to compare against, first 16 hex chars:

| Server | Target | `surface_hash` |
| --- | --- | --- |
| context7-http | `https://mcp.context7.com/mcp` | `39bc1c004279f66c` |
| deepwiki-http | `https://mcp.deepwiki.com/mcp` | `57a6aacdcae8e297` |
| everything | `npx -y @modelcontextprotocol/server-everything` | `e5889cf23ee19cfc` |
| fetch | `uvx mcp-server-fetch` | `24b5d0b33b117460` |
| filesystem | `npx -y @modelcontextprotocol/server-filesystem <dir>` | `08f53a056ccb3aa7` |
| git | `uvx mcp-server-git --repository <repo>` | `7d1ac0565240424b` |
| github-npm | `npx -y @modelcontextprotocol/server-github` | `3d1dc07dfa59b93b` |
| memory | `npx -y @modelcontextprotocol/server-memory` | `af96f076cd56a64e` |
| playwright | `npx -y @playwright/mcp@latest` | `b30c242ece6b015f` |
| seqthinking | `npx -y @modelcontextprotocol/server-sequential-thinking` | `79d9e0ee2c1e5e3a` |
| time | `uvx mcp-server-time` | `8bee13df6ca8fe91` |

Note that the remote HTTP servers and `@latest` packages can change under us; a hash
mismatch across machines on those is not necessarily a Placard bug. `fetch`, `time`,
`git`, and the pinned reference servers are the stable comparison set.

## Servers that did not enumerate

All three returned exit 3 (server unreachable), which is the correct code.

| Server | Reason |
| --- | --- |
| `@modelcontextprotocol/server-brave-search` | Exits at startup without a real `BRAVE_API_KEY` |
| `@modelcontextprotocol/server-slack` | Exits at startup without real `SLACK_BOT_TOKEN` and `SLACK_TEAM_ID` |
| `@modelcontextprotocol/server-puppeteer` | Exits at startup when it cannot launch a browser |

Slack in particular would have been a valuable R4 sample (`slack_post_message` with
`channel_id`). Worth rescanning with a real token if one is available.

## Per-server tier distribution

| Server | Tools | R0 | R1 | R2 | R3 | R4 | R5 | CHAIN_EXFIL |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| context7-http | 2 | | 2 | | | | | |
| deepwiki-http | 3 | | 3 | | | | | |
| everything | 13 | 6 | 6 | | | 1 | | |
| fetch | 1 | | | | | 1 | | |
| filesystem | 14 | 1 | 1 | 1 | | | 11 | yes (spurious) |
| git | 12 | | 11 | 1 | | | | |
| github-npm | 26 | | 15 | | 7 | | 4 | yes (spurious) |
| memory | 9 | 1 | 2 | | 4 | 2 | | yes (spurious) |
| playwright | 26 | 3 | 21 | | | 2 | | |
| seqthinking | 1 | | 1 | | | | | |
| time | 2 | | 2 | | | | | |

True positives worth noting: `fetch` R4 on `url` (Rule A), Playwright `browser_navigate`
and `browser_tabs` R4 on `url` (Rule A), and `everything`'s `gzip-file-as-resource` R4 on
`data` described as "URL or data URI" (Rule A). All correct.

## What I did not do

No rule was tuned, no field list extended, no fixture added. The brief said stop and
report. Everything above is on `main` at `e5545e0` unchanged.

## Suggested order of decisions

1. D-1 (path direction). Largest blast radius; decides whether the filesystem server is
   usable.
2. CHAIN-1 (kind vs tier). Depends on D-1 only in that fixing D-1 removes most of the
   noise; the definition problem stands regardless.
3. C-1 (`to` with `from`). Small, self-contained.
4. Reversibility list: add `sha`-with-content-sibling; decide on `dryRun`; reconsider
   `idempotentHint` as the `asserted` proxy.
5. The verb-list and `destructiveHint`-as-escalation gaps, which are additive and could
   ship as a Phase 2.1 with fixture pairs.

# Report: Phase 2.1 — classifier corrections landed, rerun against 11 real servers

**From:** Jr.
**To:** Chief
**Date:** 2026-09-18
**Re:** Brief `2026-09-18_from-chief_to-jr_phase2.1-corrections.md`, Amendment 2
**Branch:** `feature/phase-2.1-corrections`

## Summary

All nine deliverables are implemented and every acceptance criterion in the brief passes as
a test against the real server schemas (`tests/fixtures/real_servers/`, captured
2026-09-17, exercised by `tests/test_classify_real_servers.py`). The 11-server batch was
rerun today; every `surface_hash` is identical to yesterday's, so the delta below is
entirely the classifier's.

| Gate | Result |
| --- | --- |
| Tests | 396 passed (was 300) |
| Coverage on `src/` | 98% (floor 85) |
| ruff, mypy, no-invocation guard | clean |
| Self-gate | fresh mock scan byte-identical to the checked-in manifest |
| Stored `2.0` baseline | still verifies under the `2.1` build |

Three items need your eye, listed under **Flag-backs**. Two of the three conditions the
brief named did fire, and one implementation choice deviates from Amendment 2's literal
wording and is marked as such in the code.

## Delta, before → after

Same 11 servers, 109 tools, same surfaces.

| Server | Tools | Before | After | `CHAIN_EXFIL` before | after |
| --- | --- | --- | --- | --- | --- |
| filesystem | 14 | R0:1 R1:1 R2:1 R5:11 | R0:1 R1:9 R5:4 | yes (spurious) | none |
| memory | 9 | R0:1 R1:2 R3:4 R4:2 | R0:1 R1:2 R3:6 | yes (spurious) | none |
| github | 26 | R1:15 R3:7 R5:4 | R1:14 R3:10 R5:2 | yes (spurious) | none |
| playwright | 26 | R0:3 R1:21 R4:2 | R0:1 R1:7 R3:14 R4:2 R5:2 | none | yes: `browser_evaluate`, `browser_run_code_unsafe` (+ `browser_navigate`, `browser_tabs` as egress) |
| git | 12 | R1:11 R2:1 | R1:7 R3:5 | none | none |
| everything | 13 | R0:6 R1:6 R4:1 | unchanged | none | none |
| fetch | 1 | R4:1 | unchanged | none | none |
| time | 2 | R1:2 | unchanged | none | none |
| seqthinking | 1 | R1:1 | unchanged | none | none |
| deepwiki (http) | 3 | R1:3 | unchanged | none | none |
| context7 (http) | 2 | R1:2 | unchanged | none | none |

Totals: R0 11→9, R1 64→53, R2 2→0, R3 11→35, R4 6→4, R5 15→8.
`CHAIN_EXFIL`: 3 servers (all spurious) → 1 (real, via Rule H).
Kinds across the batch: write 30, destructive 25, egress 6, read_sensitive 2, code_exec 2.
Reversibility on the 47 tools at R3+: unverifiable 45, verified 1, asserted 1.

### Every tool that moved (37)

| Server | Tool | Before | After | Kinds | Reversibility | Why |
| --- | --- | --- | --- | --- | --- | --- |
| filesystem | `read_file`, `read_text_file`, `read_media_file`, `list_directory`, `list_directory_with_sizes`, `directory_tree`, `get_file_info`, `search_files` | R5 | R1 | — | — | §1: a `path` on a read is a source |
| filesystem | `move_file` | R2 | R5 | write, destructive | unverifiable | §1 cond. 3: `destination`; §7: `destructiveHint: true` |
| memory | `create_relations` | R4 | R3 | write | unverifiable | §2: `from`/`to`, no content sibling; verb `create` |
| memory | `delete_relations` | R4 | R3 | destructive | unverifiable | §2; verb `delete` |
| github | `create_or_update_file` | R5 | R3 | write | **verified** | §6: `sha` + `content` |
| github | `get_file_contents` | R5 | R1 | — | — | §1 |
| github | `merge_pull_request`, `fork_repository` | R1 | R3 | write | unverifiable | §8: verb tokens |
| git | `git_add`, `git_commit`, `git_checkout`, `git_create_branch` | R1 | R3 | write | unverifiable | §8: whole-token match |
| git | `git_reset` | R1 | R3 | destructive | unverifiable | §7 + §8 |
| git | `git_diff_unstaged` | R2 | R1 | — | — | §8: `directory` removed |
| playwright | `browser_evaluate`, `browser_run_code_unsafe` | R1 | R5 | all five | unverifiable | Rule H |
| playwright | `browser_click`, `browser_close`, `browser_drag`, `browser_drop`, `browser_file_upload`, `browser_fill_form`, `browser_handle_dialog`, `browser_hover`, `browser_navigate_back`, `browser_press_key`, `browser_resize`, `browser_select_option`, `browser_type`, `browser_webmcp_call` | R0/R1 | R3 | destructive (+write on `drop`, `type`) | unverifiable (`navigate_back`: asserted) | §7: the server declares `destructiveHint: true` on each |

Nothing else moved. `write_file`, `edit_file`, `create_directory` stay R5 (writes with an
unguarded path — the brief's "must not let a real write escape"). `push_files` and
`create_pull_request_review` stay R5; see flag-back 1.

## Deliverables, as implemented

1. **Rule D destination clause.** `DESTINATION_PATH_FIELDS = {"path"}` is gone. Conditions 2
   (content sibling) and 3 (destination-named) are decided in `schema_shape.py`; condition 1
   (an independent R3+ signal) crosses extractor boundaries, so the extractor returns the
   would-be candidate through `deferred_destination_clause` and `classify_tool` appends it
   once any other candidate has reached R3. "Same object" means "same parent JSON Pointer";
   fields in different `anyOf` branches are not siblings.
2. **Rule C `to` exemption.** Sibling `from` in the same object and no content sibling
   (`body`, `message`, `text`, `subject`, `content`, `html`). `to` only.
3. **Kind axis.** `Candidate.kinds` → `Citation.kinds` → `ToolClassification.kinds`, unioned
   in `combine.py`. No second pass. A global test asserts every kind on every tool traces to a
   citation, across the synthetic matrix and all 11 real servers. `manifest_version` is
   `"2.1"`; empty `kinds` serializes as absent, so a stored `"2.0"` baseline's
   `classification_hash` reproduces and `verify` still passes on it
   (`tests/test_manifest_version_2_0.py`, fixture is the real `2.0` mock manifest).
4. **`CHAIN_EXFIL` over kinds.** `READ_HALF_TIERS` / `EGRESS_HALF_TIERS` deleted. The
   summary names a tool that carries both halves alone. Tools-only scope statement kept.
5. **Rule H.** New `signals/code_exec.py`. Parameter names per §5, matched only when the
   parameter is unconstrained free text (an `enum` of subcommands is a selector). Name
   tokens `shell`, `unsafe`, the bigram `run`+`code`, and the stems `eval`/`exec` — the stem
   is there because `browser_evaluate` spells it `evaluate` and §5 was written against
   that tool. The `query` fail-open has the comment the brief asked for, in both the module
   docstring and at the branch.
6. **Reversibility.** `sha` with a content sibling in the same object → `verified`.
   `idempotentHint` removed; `asserted` comes from a word-start match on version, revision,
   history, trash, recycle, restore, undo in the description. `compute()` no longer takes
   annotations.
7. **Annotations escalate.** `signals/annotations.py` now has a real `extract`:
   `destructiveHint: true` → R3 candidate, kind `destructive`, signal `declared_annotations`.
   `find_disagreements` still fires only on declared-safer-than-inferred; `readOnlyHint: true`
   on a `code_exec` tool gets the severest reading.
8. **Verb matching.** Whole-token match over snake, kebab, dotted, and camel boundaries.
   `reset` joined the destructive set; `merge`, `push`, `checkout`, `commit`, `fork`, `move`,
   `rename` joined the write set. `settings_get` and `toggle-subscriber-updates` do not match.
9. **`directory` removed** from the sensitivity vocabulary.

Docs: Amendment 2 folded into `docs/TAXONOMY.md` (Rule D rewrite, Rule C exemption, a Kinds
section, Rule H, `CHAIN_EXFIL` redefinition, the declared-vs-inferred table, reversibility
evidence); AGENTS.md roadmap and taxonomy section; README status and the delta table;
`classify/README.md`. `TAXONOMY-amendment-2.md` moved to `docs/` next to Amendment 1.

## Flag-backs

### 1. Rule D condition 2 promotes a *reference* path next to a body — `create_pull_request_review`

GitHub `create_pull_request_review` takes `comments[].{path, position, body}`. `path` here
names the file a review comment is *about*; nothing is written to it. Condition 2 sees `path`
with sibling `body` and forces R5. It is a write (R3 is right); R5 unverifiable is not.
`push_files(files[].{path, content})` is the same shape and *is* a file write, so the
condition cannot be narrowed by shape alone. Options: (a) accept — an over-tier on a write
is the cheap direction, and this is one tool in 109; (b) drop `body` from Rule D's
content-sibling list, keeping it in Rule C's — `body` is a message body far more often than
a file body, and `content`/`contents`/`data`/`edits`/`text` still cover file writes. I lean
(b) but did not apply it. The brief says stop and report with the schema:

```json
{"comments": {"type": "array", "items": {"anyOf": [{"type": "object", "properties":
  {"path": {"type": "string"}, "position": {"type": "number"}, "body": {"type": "string"}}}]}}}
```

### 2. Description-derived `read_sensitive` is withheld when the description opens with an action verb

Amendment 2 §3 derives `read_sensitive` from "sensitivity-description evidence." Read
literally, `send_email` — description "Send an email" — carries `read_sensitive` (from
`email`) and `egress` (from `to`), so every mail sender raises `CHAIN_EXFIL` alone, through
the weakest signal in the taxonomy. The taxonomy's own definition of the description signal
is "*a read* whose description names one of these," so I gated the kind (not the R2 tier
floor, which still applies) on the description not opening with a closed list of action
verbs (`send`, `post`, `create`, `delete`, `update`, ...). The mock server's `send_email`
and the `create_calendar_event` fixture depend on this. It is marked as a flagged
implementation choice in `signals/description.py` and in the taxonomy; if you would rather
take §3 literally and accept the self-chain, it is a one-line revert.

### 3. `asserted` is empty in practice — the third condition in the brief

Across the 11 servers, 47 tools sit at R3 or above. 45 are `unverifiable`, 1 is `verified`
(GitHub `create_or_update_file`), and exactly 1 is `asserted`: Playwright's
`browser_navigate_back`, whose description is "Go back to the previous page **in history**."
That is browser history, not revision history — a keyword false positive, and the only
`asserted` in the batch. So the honest count is 0 of 47. The brief's own words: "a state that
never occurs is a state worth deleting, and that is a taxonomy decision rather than yours or
mine to make silently." Two options: delete `asserted` and go to a two-state field, or keep
it and accept it will be rare until a server with real trash/restore semantics (Google
Drive, Notion) enters the batch. I have no strong lean; the keyword list is cheap to keep.

### Observations, not decisions

- **§7 takes Playwright at its word.** It declares `destructiveHint: true` on `hover`,
  `resize`, `close`, `press_key`, `navigate_back`. Fourteen tools rose to R3 on that alone.
  This is the amendment's intended reading — a claim against interest is trusted — and the
  cost falls on the over-declaring server, not on us. Worth knowing it happens on a
  mainstream server.
- **The `query` discriminator held.** Six real `query` parameters (GitHub search ×4,
  memory `search_nodes`, context7 ×2), zero received `code_exec`. No raw-query tool was in
  the batch to test the positive side beyond the synthetic fixtures.
- **`read_sensitive` fired on nothing but the two `code_exec` tools.** No server in the batch
  is a mail, calendar, or people-directory server, so the sensitivity vocabulary had nothing
  to match. The `CHAIN_EXFIL` read half is untested against a real R2 server; Slack with a
  real token, or a Gmail/Drive server, would close that.
- **Rule D condition 1 did the work the brief predicted.** `create_directory(path)` stays R5
  through verb → condition 1, not through the old blanket match.

## Still open

- Cross-machine byte-identical check. Today's rerun reproduced every one of yesterday's
  eleven `surface_hash` values on this machine, 24 hours apart, including the remote HTTP and
  `@latest` targets. The second machine is still needed.
- Slack with a real token.

## Not done, by instruction

Injection heuristics, SARIF, GitHub Action packaging, signing, the public index, resource and
prompt classification, additional chain types, and the multi-server config scan (Phase 6).

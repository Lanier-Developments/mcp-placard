# Decisions: Phase 2.2 — the three Phase 2.1 flag-backs

**From:** Chief
**To:** Jr.
**Date:** 2026-09-18
**Re:** Your Phase 2.1 report, branch `feature/phase-2.1-corrections`

Part 1 is taxonomy text — fold it into `docs/TAXONOMY.md` as Amendment 3. Part 2 is the work
order. All three are small; this is not a phase, it is the tail of 2.1.

The corrections landed correctly. The filesystem server going from eleven R5s to four, with the
four being real writes, is the result the amendment was aimed at, and `create_or_update_file`
reaching `verified` on `sha` confirms the evidence list was the right shape rather than a lucky
guess.

---

## Part 1 — Amendment 3

### 3.1 `body` leaves Rule D's content-sibling list

Your option (b). `create_pull_request_review` takes `comments[].{path, position, body}`, where
`path` names the file a comment is *about* and nothing is written to it. `push_files` is the same
shape and is a real write, so the two cannot be told apart structurally — but they can be told
apart by vocabulary, and you identified the right word.

> Rule D's content-sibling list is `content`, `contents`, `data`, `text`, `edits`. `body` is
> removed. Rule C's content-sibling list is unchanged and still includes `body`.

`body` names a message or comment body far more often than a file body, which is exactly why it
belongs in Rule C and not in Rule D. A server that does use `body` for file content loses only
condition 2; a write verb reaches it through condition 1 and a destination-named field through
condition 3.

### 3.2 `read_sensitive` means *returns* sensitive data to the caller

Your gate is correct and is promoted from an implementation choice to a stated rule. The
justification is cleaner than the verb list makes it look, and the taxonomy should carry it:

> `read_sensitive` asserts that a tool hands sensitive data back to the caller. A description
> naming a sensitive domain establishes the R2 tier floor, but confers the kind only where the
> tool is returning rather than acting — that is, where the description does not open with an
> action verb.
>
> A tool that moves sensitive data outward without returning it to the caller — `send_email`,
> `forward_message`, `share_file` — is not `read_sensitive`. It is `egress` at R4, which is
> already the stronger finding.

That last paragraph is the part worth writing down, because it answers the objection the verb gate
invites. `forward_email` looks like a one-tool exfiltration chain and is missed by the gate, but
the agent never sees the message content, so there is no chain to catch — the tool is dangerous as
egress and is classified as such. Losing the kind costs nothing.

Keep the verb list closed and short. It does not need `forward` or `share` for the reason above.

### 3.3 `asserted` survives, on tightened evidence

Keep the state. The batch contains no document-management server, and Drive, Notion, Confluence,
and versioned object stores are precisely where real trash-and-restore semantics live. Deleting a
state now and restoring it when those servers arrive costs a manifest version bump and a
consumer-visible schema change to buy nothing.

`browser_navigate_back` is not evidence against the state; it is evidence against the keyword list.
Bare `history` matches browser history and bare `version` matches a server version string.

> `asserted` requires a phrase from a closed list: `version history`, `revision history`,
> `previous version`, `restore`, `undo`, `trash`, `recycle bin`, `soft delete`, `recoverable`.
> Bare `history` and bare `version` are removed.

Standing decision so this does not come back as an open question: if `asserted` is still empty
after a document-management server has been scanned, the state is deleted then, in one manifest
version bump alongside whatever else is changing. Until that scan happens the question is not ripe.

---

## Part 2 — Work order

1. Remove `body` from Rule D's content-sibling list. `create_pull_request_review` should land R3
   `write` `unverifiable`; `push_files` must stay R5. Both as real-server fixtures.
2. Promote the `read_sensitive` gate from a flagged implementation choice to the rule in 3.2 —
   the code comment becomes a citation of the taxonomy rather than an apology for deviating.
   Keep the verb list closed; do not add `forward` or `share`.
3. Tighten the `asserted` phrase list per 3.3. `browser_navigate_back` returns to `unverifiable`,
   and `asserted` is 0 of 47 across the batch, which is the honest number.
4. Rerun the 11-server batch and append the corrected distribution to the delta table. Three tools
   should move; nothing else.

No manifest version bump — none of these changes the format.

## Note for the record: Playwright over-declares

Fourteen Playwright tools rose to R3 on `destructiveHint: true` alone, including `hover`,
`resize`, and `press_key`. That is the amendment working as intended, and the cost falls on the
over-declaring server.

It is also a finding in its own right, and worth keeping: the annotation is used inconsistently
across the ecosystem, by a mainstream server, in the conservative direction. That is a point in
favor of the declared-versus-inferred split existing at all, and it belongs in the Phase 5 index
write-up rather than being quietly absorbed as noise.

## Still open, unchanged

Cross-machine byte-identical check needs the second machine. The `CHAIN_EXFIL` read half remains
untested against a real R2 server — Slack with a token, or any mail, calendar, or people-directory
server, closes that and is the most valuable single addition to the batch.

# TAXONOMY.md — Amendment 1

Status: adopted, and folded into `docs/TAXONOMY.md` (Rules A-F, the `CHAIN_EXFIL` finding, the
revised fixture matrix). `docs/TAXONOMY.md` is authoritative; this document is retained as the
original review record.
Origin: independent cross-family review, adjudicated by Chief. Four boundary findings accepted
(two with modified wording), one rejected with a substitute mechanism, one finding reclassified as
a specification defect in AGENTS.md rather than a taxonomy defect.

---

## 1. Amended and new rules

### Rule A — Caller-influenced outbound targets are R4

> Any parameter that lets the caller specify or influence the destination of a request the server
> makes outward is R4 (Egress), regardless of the tool's verb and regardless of
> `readOnlyHint: true`.

Rationale: a tool named `get_link_preview(url)` performs an outbound fetch to a caller-supplied
destination. An agent induced to call it with a sensitive value appended to a query string has
exfiltrated data through what the server honestly believes is a read. The verb and the annotation
are both accurate and both irrelevant.

Scope limit, deliberate: this rule covers caller *control of destination*, not caller supply of an
identifier. `get_user(user_id)` where the ID is opaque and resolved against the server's own store
is not egress. The test is whether the caller can steer where the request goes, not whether the
caller supplied a string.

### Rule B — R0 requires a closed input surface

> R0 is available only to tools whose input schema is empty, or consists exclusively of closed
> enums, booleans, and values constrained by a tight pattern. Any unconstrained free-text
> parameter (`type: string` with no `enum` and no restrictive `pattern`) places the tool at R1 or
> higher.

Consequence, accepted: R0 becomes nearly empty in practice. That is the correct outcome. R0 means
"cannot be steered," and a free-text parameter is steering.

### Rule C — External communication target fields force R4

> Any input field accepting an external communication target forces R4 regardless of the primary
> verb. The recognized fields are: `to`, `cc`, `bcc`, `reply_to`, `recipient`, `recipients`,
> `attendees`, `webhook_url`, `callback_url`, `notify_url`, `slack_channel`, `channel`,
> `phone`, `sms_to`.

This generalizes the existing `create_calendar_event` / `attendees` promotion to creation and
update schemas broadly: `create_issue(webhook_url)` is R4, not R3.

The list is explicit and closed by design. A heuristic over "fields that might notify someone"
pulls `assignee`, `owner`, `reviewer`, and `mentions` into R4 and empties the tier of meaning.
Additions to this list are a deliberate change, made by editing this rule.

### Rule D — Reversibility carries a confidence state

Rule 4 previously read that reversibility is a property of the server, not the verb — overwrite
with revision history is R3, without it R5. The review correctly observed that a scanner which
never invokes a tool cannot verify at scan time whether revision history exists, and that trusting
the absence of evidence amounts to accepting a server-side promise.

The proposed remedy — default all overwrites to R5 — is rejected. It would place most of the write
surface of most servers into the top tier, cause the CI gate to fire continuously, and end with
somebody turning the gate off. Pessimism is not precision.

Adopted instead: reversibility becomes an explicit confidence state, and schema evidence breaks the
tie.

> Every tool at R3 or above carries a `reversibility` field with one of three values:
>
> - `verified` — the input schema itself evidences a guarded write
> - `asserted` — the server declares or implies reversibility, unconfirmed
> - `unverifiable` — no evidence either way
>
> Schema evidence for `verified`: presence of an optimistic-concurrency parameter — `if_match`,
> `etag`, `version`, `expected_revision`, `if_unmodified_since`, or an equivalent.
>
> Schema evidence forcing R5 regardless of other signals: presence of `force`, `overwrite`,
> `recursive`, `permanent`, `purge`, or `skip_trash` as a boolean the caller can set true; or a
> destination path parameter with no concurrency token present.

An unguarded `write_note(path, content)` therefore lands at R5 on evidence, not on pessimism, while
`update_record(id, body, if_match)` lands at R3 `verified`. Whether `asserted` and `unverifiable`
writes block CI is a decision for the consuming repo's ceiling configuration, not a decision this
taxonomy makes for everyone.

### Rule E — Host-pinning is recognized by form, not by regex analysis

The review flagged that a naive classifier reading `pattern` as a host constraint can be defeated
by an unescaped dot or a permissive subdomain wildcard, so that
`^https://docs.internal.example.com` appears to pin a host while admitting
`https://docsXinternalYexampleZcom.attacker.com`.

Accepted, and extended. The scanner will not attempt to reason about whether an arbitrary regex is
safe; a classifier that analyzes regex anchoring incorrectly is more dangerous than one that
declines to analyze it at all.

> A `pattern` constrains a host only if it matches one of a short allowlist of recognized pattern
> forms — anchored at start, literal scheme, fully escaped literal host, no alternation, no
> unbounded wildcard in the host portion. Every other pattern is treated as unconstrained, and the
> parameter is therefore a caller-influenced outbound target under Rule A.

The allowlist of forms lives in `classify/patterns.py` with a fixture per accepted form and a
fixture per rejected form.

### Rule F — Signals combine as a monotonic maximum

This was raised as a classifier implementation trap — that a weak signal such as the verb `get_`
might suppress a strong schema signal such as `properties.url`. The concern is real; the premise is
a specification defect on our side.

AGENTS.md states that a tool receives the highest tier any signal supports, which is a maximum and
makes weight ordering irrelevant to escalation. It then describes the signal classes "in decreasing
weight," which invites an implementer to build a weighted score. A weighted score produces a fuzzy
number where the design calls for a monotonic maximum with cited evidence.

> Tier assignment is the maximum tier supported by any signal. Signal ordering exists only to
> determine which signal is cited first in the finding, and to resolve which evidence is recorded
> when several support the same tier. Ordering never reduces a tier.

Downgrades remain impossible except through an explicit allowlist entry in the consuming repo's
configuration, and the manifest records that an override applied.

**AGENTS.md edit required:** strike "in decreasing weight" from the Risk Taxonomy section and
replace with "monotonic maximum over signals; ordering governs citation only."

---

## 2. New server-level finding: chained capability

Not raised in review. Added by Chief.

The taxonomy classifies tools. Blast radius is compositional, and the property that matters to a
security reviewer is not the maximum tier present but the combinations available. A server
exposing an R2 sensitive read alongside an R4 egress tool contains a complete exfiltration chain,
and neither tool alone need be alarming enough to cross a ceiling.

> The manifest carries server-level findings alongside per-tool classification. Phase 2 implements
> one: `CHAIN_EXFIL`, raised when the server exposes at least one R2-or-above read and at least one
> R4 egress. The finding names the specific tools that form each chain.

Further chains — R2 read plus R3 write to a caller-named destination, R1 enumeration feeding an R5
destructive operation — are deliberately deferred. One chain, implemented well and with a low
false-positive rate, is worth more than five speculative ones.

This is likely the most defensible single output the tool produces, because it says something no
per-tool review and no server's own documentation says.

---

## 3. Revised Phase 2 fixture matrix

Two worked examples and one near-miss pair per tier. Adopted from review with one substitution.

| Tier | Example 1 | Example 2 | Near-miss pair |
| --- | --- | --- | --- |
| R0 | `describe_server` | `list_supported_formats` | `search_public_docs(query: string)` → R1 (Rule B) |
| R1 | `search_documents` | `get_build_status` | `get_build_status(include_secrets)` → R2 |
| R2 | `read_inbox` | `list_directory_users` | `get_link_preview(url)` → R4 (Rule A) |
| R3 | `create_issue` | `update_record(id, body, if_match)` | `create_issue(webhook_url)` → R4 (Rule C) |
| R4 | `send_email` | `fetch_url` | `fetch_doc` with recognized host-pinned form → R1 (Rule E) |
| R5 | `delete_workspace` | `write_note(path, content)` unguarded | `rotate_display_name` → R3 |

Substitution: the review proposed `whoami → R1` as the R2 near-miss. Rejected — in enterprise
servers `whoami` routinely returns organization, group membership, roles, and email address, which
is squarely R2. It is a weak near-miss because the intuitive answer is the wrong one for the wrong
reason. `get_link_preview` replaces it and exercises Rule A, which is the newest and least tested
boundary.

Additional fixtures required beyond the matrix:

- One tool per recognized host-pinning form and one per rejected form (Rule E).
- One `verified`, one `asserted`, and one `unverifiable` reversibility case (Rule D).
- One declared-vs-inferred disagreement: a tool with `readOnlyHint: true` whose schema carries a
  `to` field.
- One server surface that raises `CHAIN_EXFIL` and one that deliberately does not, differing by a
  single tool.

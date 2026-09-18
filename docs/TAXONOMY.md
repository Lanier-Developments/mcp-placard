# Risk Taxonomy

The blast radius of a tool is **what an agent can do to the world by calling it once,
with arguments the agent chose**. Not what the tool is for. Not what the server
promises it does. What the call can reach.

This document defines the six tiers, then works two concrete examples through each
one. Phase 2's classifier is written against these examples, so they are written to
be implementable: each carries a tool name, an input schema fragment, the signals
that decide it, and — where the boundary is genuinely contested — the near-miss that
sits one tier away.

## Status

Implemented in `classify/`. Phase 1 assigned **no tiers** — every tool carried the
literal tier `unclassified`, and a `"1.0"` manifest still reads that way (see
`manifest/io.py`'s backward-compatibility note). `classify.classify_manifest` now
assigns every tool a real R0-R5 tier against this specification;
`tests/test_classify_fixture_matrix.py` is the fixture matrix below, as code.

`TAXONOMY-amendment-1.md` and Part 1 of the 2026-09-16 addendum are folded into this
document (Rules A-G below, the revised fixture matrix, and `CHAIN_EXFIL`).
`TAXONOMY-amendment-2.md` (2026-09-18, adjudicating the first real-server batch) is
folded in as well: the Rule D destination clause, the Rule C `to` exemption, the
kind axis, `CHAIN_EXFIL` over kinds, Rule H, the revised reversibility evidence,
annotation escalation, and the sensitivity vocabulary. All source documents are
retained as the original review record; this document is authoritative wherever
they would otherwise be consulted separately.

## The tiers

Tiers are ordered. **A tool receives the highest tier any signal supports.** A tool
that reads calendars *and* can post a webhook is R4, not R2 — the read does not
average against the egress.

| Tier | Name | Meaning |
| --- | --- | --- |
| R0 | Inert | No side effects, no data return of consequence — metadata, schema, help |
| R1 | Read-scoped | Reads data inside the server's own declared domain |
| R2 | Read-sensitive | Reads user or organizational data — mail, files, calendar, directory |
| R3 | Write-scoped | Creates or mutates within the server's domain, reversibly |
| R4 | Egress | Moves data outward — send, post, publish, webhook, arbitrary-URL fetch |
| R5 | Irreversible | Delete, purge, revoke, rotate, transfer funds, write credentials |

## Signals

Four signal classes feed a tier. **Tier assignment is a monotonic maximum over
signals — signals do not average, and ordering never reduces a tier** (Rule F).
Listing them in a fixed order below still matters: ordering decides which signal is
cited first in a finding when several support the same tier, and roughly tracks how
hard each one is to fake.

1. **Input schema shape.** The hardest signal to fake while remaining functional.
   Fields named like `to`, `recipient`, `url`, `webhook`, `amount`, `path`, `force`,
   `confirm`, `permanent`, `scope`. Also the *absence* of constraint: a `path` with no
   prefix pattern reaches further than one pinned to `^notes/`. Traverses the
   complete schema — nested objects, arrays, and `$ref`/`allOf`/`anyOf`/`oneOf`
   composition — per Rule G below, never just the top level.
2. **Declared annotations.** `readOnlyHint`, `destructiveHint`, `idempotentHint`,
   `openWorldHint` — supplied by the party being audited. Evidence, never truth. A
   declaration *against* interest (`destructiveHint: true`) is a floor of R3 and kind
   `destructive` (Amendment 2 §7); a declaration of safety never moves a tier.
3. **Tool name verb.** `get_`, `list_`, `search_` versus `send_`, `post_`, `delete_`,
   `revoke_`, `transfer_`. Cheap and usually honest, trivially renameable.
4. **Description text.** The weakest signal for tiering, and the *only* thing that
   Phase 3's injection heuristics care about. A description is prose written by the
   audited party; it is the last thing that should move a tier. The sensitive-domain
   vocabulary is `mail`, `inbox`, `email`, `calendar`, `correspondence`, `contact`,
   `employee`, `roster`; `directory` was removed by Amendment 2 §8 (on filesystem and
   git servers it means a folder). A match floors the tool at R2; it establishes kind
   `read_sensitive` only when the description does not open with an action verb —
   `send_email` touches mail but does not read it (an implementation choice, flagged
   in the Phase 2.1 report).

Every assigned tier must cite the signals that produced it. A tier without stated
reasoning is an opinion, not a finding.

## Declared vs inferred

Annotations are recorded as declared and compared against the inferred tier.
Disagreement is itself a finding, and the interesting direction is one-way:

| Declared | Inferred | Reading |
| --- | --- | --- |
| `readOnlyHint: true` | R3+ | **Finding.** The server claims safety its schema does not support. |
| `destructiveHint: false` | R5 | **Finding.** Same shape, stated more specifically. |
| `openWorldHint: false` | R4 | **Finding.** A closed world does not take a `url`. |
| `readOnlyHint: true` | R5 with kind `code_exec` | **Finding, highest severity.** A read-only tool that executes caller-supplied code (Rule H). |
| (absent) | R5 | Not a disagreement, but worth surfacing: high tier, no declaration. |
| `destructiveHint: true` | R1 | Not a finding — it **escalates** (Amendment 2 §7): floor R3, kind `destructive`. |

**Never silently downgrade a tier because a server declares itself safe.** A
downgrade requires an explicit allowlist entry in the consuming repo's config, and
the manifest records that an override applied.

> A server annotation may raise a tier and may contribute a kind. It may never reduce
> a tier. `destructiveHint: true` establishes kind `destructive` and a floor of R3.

Self-declared safety is a claim the declarer benefits from, and is treated as
evidence to be checked. Self-declared danger is a claim against interest, and is the
most trustworthy signal a server gives us.

## Amendment 1 — adopted rules (A-G)

Adopted from independent cross-family review, adjudicated by Chief, plus one addendum
rule (G) from a second review pass. Fixtures for these rules are listed in the
revised fixture matrix below.

### Rule A — Caller-influenced outbound targets are R4

> Any parameter that lets the caller specify or influence the destination of a
> request the server makes outward is R4 (Egress), regardless of the tool's verb and
> regardless of `readOnlyHint: true`.

Rationale: a tool named `get_link_preview(url)` performs an outbound fetch to a
caller-supplied destination. An agent induced to call it with a sensitive value
appended to a query string has exfiltrated data through what the server honestly
believes is a read. The verb and the annotation are both accurate and both
irrelevant.

Scope limit, deliberate: this rule covers caller *control of destination*, not caller
supply of an identifier. `get_user(user_id)` where the ID is opaque and resolved
against the server's own store is not egress. The test is whether the caller can
steer where the request goes, not whether the caller supplied a string.

### Rule B — R0 requires a closed input surface

> R0 is available only to tools whose input schema is empty, or consists exclusively
> of closed enums, booleans, and values constrained by a tight pattern. Any
> unconstrained free-text parameter (`type: string` with no `enum` and no restrictive
> `pattern`) places the tool at R1 or higher.

Consequence, accepted: R0 becomes nearly empty in practice. That is the correct
outcome. R0 means "cannot be steered," and a free-text parameter is steering.

### Rule C — External communication target fields force R4

> Any input field accepting an external communication target forces R4 regardless of
> the primary verb. The recognized fields are: `to`, `cc`, `bcc`, `reply_to`,
> `recipient`, `recipients`, `attendees`, `webhook_url`, `callback_url`,
> `notify_url`, `slack_channel`, `channel`, `phone`, `sms_to`.

This generalizes the `create_calendar_event` / `attendees` promotion to creation and
update schemas broadly: `create_issue(webhook_url)` is R4, not R3.

The list is explicit and closed by design. A heuristic over "fields that might notify
someone" pulls `assignee`, `owner`, `reviewer`, and `mentions` into R4 and empties the
tier of meaning. Additions to this list are a deliberate change, made by editing this
rule.

> **Rule C — exemption (Amendment 2 §2).** `to` is not a communication target when a
> sibling `from` exists in the same object **and** no content-carrying sibling is
> present (`body`, `message`, `text`, `subject`, `content`, `html`). Messages carry
> bodies; edges and ranges do not.

The `from`/`to` pair is a common idiom for edges, ranges, diffs, intervals, and
internal transfers — the memory server's `create_relations(relations[].{from, to,
relationType})` is a graph edge, not a recipient. The obvious exemption — a sibling
`from` alone — would release `send_email(from, to, subject, body)`, the exact tool
this rule exists to catch; content is the better discriminator. The exemption applies
to `to` only.

### Rule D — Reversibility carries a confidence state

A scanner that never invokes a tool cannot verify at scan time whether revision
history exists, so trusting the absence of evidence would amount to accepting a
server-side promise. The rejected alternative — default all overwrites to R5 — would
place most of the write surface of most servers into the top tier, fire the CI gate
continuously, and end with somebody turning the gate off. Pessimism is not precision.

Adopted instead: reversibility becomes an explicit confidence state, and schema
evidence breaks the tie.

> Every tool at R3 or above carries a `reversibility` field with one of three values:
>
> - `verified` — the input schema itself evidences a guarded write
> - `asserted` — the server's description claims it retains recoverable state, unconfirmed
> - `unverifiable` — no evidence either way
>
> Schema evidence for `verified`: presence of an optimistic-concurrency parameter —
> `if_match`, `etag`, `version`, `expected_revision`, `if_unmodified_since`, or an
> equivalent — anywhere in the schema; or a `sha` parameter accompanied by a
> content-carrying sibling in the same object (Amendment 2 §6 — GitHub's Contents API
> idiom; `sha` alone is a plain commit reference on read tools).
>
> Description evidence for `asserted`: the server states that recoverable state is
> retained — version, revision, history, trash, recycle, restore, undo. Absent that,
> and absent `verified` evidence, the value is `unverifiable`.
>
> Schema evidence forcing R5 regardless of other signals: presence of `force`,
> `overwrite`, `recursive`, `permanent`, `purge`, or `skip_trash` as a boolean the
> caller can set true.
>
> **Destination clause (Amendment 2 §1).** A path-like parameter with no concurrency
> token present forces R5 only when the tool is already established as writing, by
> at least one of:
>
> - an independent signal placing the tool at R3 or above;
> - a content-carrying sibling in the same object — `content`, `body`, `data`, `text`,
>   `edits`, `contents`;
> - the parameter name itself denoting a destination — `destination`, `dest`,
>   `target_path`, `output_path`, `to_path`, `new_path`.
>
> A read carrying a path parameter is classified by Rule B and the sensitivity
> signals, and stops there.

An unguarded `write_note(path, content)` therefore lands at R5 on evidence, not on
pessimism, while `update_record(id, body, if_match)` lands at R3 `verified`. Whether
`asserted` and `unverifiable` writes block CI is a decision for the consuming repo's
ceiling configuration, not a decision this taxonomy makes for everyone.

The destination clause originally read "a destination path parameter with no
concurrency token present," and the first implementation dropped the word
*destination*: any string named `path`, anywhere, forced R5, which put eight of the
reference filesystem server's fourteen tools — all reads — at R5, each with a
`readOnlyHint` disagreement. A `path` on `read_file` is a source; the rule was never
about sources. The three-condition form also closes the `move_file(source,
destination)` gap, which was landing at R2 because the clause keyed on `path` alone.

Residual risk, accepted and recorded: a tool named `get_file` that in fact writes,
carrying neither a content sibling nor a destination-named field, evades R5. It still
classifies at R1 or above, its schema and description are still hashed, and any later
change to either is still a diff finding. This is the same exposure every
verb-derived signal carries.

Rejected as `verified` evidence: `dryRun` (a preview flag establishes that the tool
can be run without effect, not that the real call is reversible; no fourth state is
created for it) and `commitId` (too weak). Removed as the source of `asserted`:
`idempotentHint: true` — an idempotent delete is not a reversible one. `unverifiable`
becoming the common case is the honest outcome; it is what the scanner actually
knows.

### Rule E — Host-pinning is recognized by form, not by regex analysis

A naive classifier reading `pattern` as a host constraint can be defeated by an
unescaped dot or a permissive subdomain wildcard, so that
`^https://docs.internal.example.com` appears to pin a host while admitting
`https://docsXinternalYexampleZcom.attacker.com`. The scanner will not attempt to
reason about whether an arbitrary regex is safe; a classifier that analyzes regex
anchoring incorrectly is more dangerous than one that declines to analyze it at all.

> A `pattern` constrains a host only if it matches one of a short allowlist of
> recognized pattern forms — anchored at start, literal scheme, fully escaped literal
> host, no alternation, no unbounded wildcard in the host portion. Every other
> pattern is treated as unconstrained, and the parameter is therefore a
> caller-influenced outbound target under Rule A.

The allowlist of forms lives in `classify/patterns.py` with a fixture per accepted
form and a fixture per rejected form.

### Rule F — Signals combine as a monotonic maximum

AGENTS.md states that a tool receives the highest tier any signal supports, which is
a maximum and makes weight ordering irrelevant to escalation. Describing signal
classes "in decreasing weight" invites an implementer to build a weighted score
instead — a fuzzy number where the design calls for a monotonic maximum with cited
evidence.

> Tier assignment is the maximum tier supported by any signal. Signal ordering exists
> only to determine which signal is cited first in the finding, and to resolve which
> evidence is recorded when several support the same tier. Ordering never reduces a
> tier.

Downgrades remain impossible except through an explicit allowlist entry in the
consuming repo's configuration, and the manifest records that an override applied.

### Rule G — Schema-shape signals traverse the full schema

Rule A's caller-influenced outbound targets, Rule C's communication-target fields,
and Rule D's concurrency tokens all evade detection identically if matching stops at
the top level.

> Schema-shape signals traverse the complete input schema: nested objects, arrays of
> objects, and `$ref`, `allOf`, `anyOf`, and `oneOf` composition. Matching property
> names at the top level only is insufficient — a `to` field three levels inside an
> `allOf` branch is a communication target and carries the same consequence as one at
> the root.
>
> Traversal carries a depth cap and `$ref` cycle protection. A schema that exceeds
> the depth cap, contains a `$ref` cycle, or contains an unresolvable `$ref` is
> treated as **unconstrained**: the tool is classified as though the signal matched,
> and the finding cites the traversal failure as its evidence.

The fail-closed clause is load-bearing. A schema too complex or too indirect to
traverse is a schema whose safety cannot be established, and a classifier that shrugs
and returns R1 in that case is defeated by any server willing to nest one level
deeper than the parser goes. Depth cap and cycle protection exist to keep the scanner
from hanging, not to create an exemption.

Composition keywords are where real schemas put things. `anyOf` branches in
particular are how a single tool presents two different call shapes, and it is
entirely ordinary for only one of them to carry the dangerous field.

Every schema-shape signal — not any single rule above — is implemented against a
shared traversal utility (`classify/schema_walk.py`) rather than reimplementing field
matching per rule; see AGENTS.md and the Phase 2 brief.

## Kinds — a second axis (Amendment 2 §3)

The tier ladder must stay totally ordered to function as a CI ceiling. But R3 is a
write and R5 is not egress, and a chain finding that expresses "read" and "egress"
as tier sets names the wrong tools. The second dimension belongs somewhere else.

> **Every tool carries a `kinds` set alongside its tier.** Kinds are derived from the
> evidence that produced the classification, not from the tier:
>
> | Kind | Derived from |
> | --- | --- |
> | `read_sensitive` | sensitivity-field or sensitivity-description evidence |
> | `egress` | Rule A (caller-influenced outbound target) or Rule C (communication target) |
> | `write` | write-verb, content-carrying field, or destination-path evidence |
> | `destructive` | destructive-verb evidence, R5-forcing boolean, or `destructiveHint: true` |
> | `code_exec` | Rule H below |
>
> A tool may carry several kinds. An empty set is legal and means no kind-bearing
> evidence was found. Kinds never affect tier and tier never affects kinds.

Kinds are derived inside the signal extractors, where the evidence already lives,
and every kind on a tool traces back to at least one citation carrying it — a kind
with no citation is as much a bug as a tier with none. Kinds are the extension point
for the chain types deferred in Amendment 1: adding one later is a predicate over
kinds rather than a new tier-set heuristic. An operator override lowers a tier; it
never changes what a tool does.

### Rule H — caller-supplied code execution (Amendment 2 §5)

A tool that executes caller-supplied code has unbounded blast radius. It does not
merely sit at the top of the ladder — it subsumes every other kind, because code can
read, write, destroy, and exfiltrate by construction. The ladder describes what a
tool *does*; this describes what a tool *permits*.

> **Rule H.** A tool accepting caller-supplied code, script, shell command, or raw
> query text classifies R5 with kind `code_exec`, and additionally carries
> `read_sensitive`, `write`, `destructive`, and `egress`.
>
> Signals: parameter names `code`, `script`, `command`, `cmd`, `shell`, `expression`,
> `eval` where the parameter is unconstrained free text; `query` where the description
> indicates raw query text rather than a search string; tool-name tokens `eval`,
> `exec`, `run_code`, `execute`, `shell`, `unsafe` (`eval` and `exec` matched by stem,
> so `evaluate` and `execute` count).
>
> `readOnlyHint: true` on such a tool is a disagreement finding of the highest
> severity available.

Because `code_exec` carries both chain halves, any server exposing one raises
`CHAIN_EXFIL` alone. That is correct and is the intended reading: a server with an
eval tool is a server where the chain question is already settled.

**The one deliberate fail-open in the taxonomy.** A `query` parameter on a search
tool is ordinary free text under Rule B and must not reach R5. The discriminator is
the description, and where the description is ambiguous the tool does *not* receive
`code_exec`. An R5 false positive on every search tool in existence would destroy the
tool's usefulness faster than the false negative costs us. Widening that signal is
how every search tool in the ecosystem becomes R5; if it proves unworkable against
real descriptions, report rather than widen.

## Server-level findings — `CHAIN_EXFIL`

The taxonomy above classifies tools. Blast radius is compositional, and the property
that matters to a security reviewer is not the maximum tier present but the
combinations available. A server exposing an R2 sensitive read alongside an R4
egress tool contains a complete exfiltration chain, and neither tool alone need be
alarming enough to cross a ceiling.

> The manifest carries server-level findings alongside per-tool classification. Phase
> 2 implements one: `CHAIN_EXFIL`, raised when the server exposes at least one tool
> with kind `read_sensitive` and at least one tool with kind `egress`. Tier is not
> consulted. A single tool carrying both kinds raises the finding on its own. The
> finding names the specific tools that form each chain.

Amendment 2 §4 redefined the halves over kinds. The Phase 2 implementation had to
express "read" as `{R2, R3}` and "egress" as `{R4, R5}` because the ladder offered no
other axis; every chain the first real-server batch raised was spurious as a result
(R3 writes as the "read" half, R5 path writes as the "egress" half), and the true
count was 0 of 11.

Further chains — R2 read plus R3 write to a caller-named destination, R1 enumeration
feeding an R5 destructive operation — are deliberately deferred. One chain,
implemented well and with a low false-positive rate, is worth more than five
speculative ones. This is likely the most defensible single output the tool
produces, because it says something no per-tool review and no server's own
documentation says.

> `CHAIN_EXFIL` evaluates tools only. Resources and prompts are enumerated but
> unclassified in Phase 2, so a chain whose read half is a resource — a server
> exposing mail contents or file bodies as a resource alongside an R4 egress tool —
> is not detected. This is a known gap, not an assertion of safety. It closes when
> resource classification lands. The finding's own output states this tools-only
> scope, so a reader learns the boundary from the report, not only from this
> document. The same limitation is recorded in `docs/THREAT_MODEL.md` alongside the
> named adversaries once `CHAIN_EXFIL` ships.

---

# Worked examples

## R0 — Inert

*No side effects, and no data of consequence returned. Calling it teaches the agent
about the server, not about the world.*

### R0 example 1 — `describe_server`

```json
{ "type": "object", "properties": {}, "additionalProperties": false }
```

**Tier: R0.** An empty closed schema is the clearest R0 signal there is: the agent
cannot parameterize the call, so it cannot steer it anywhere. The return is the
server's own name, version, and configuration — facts about the tool surface, which
the agent already effectively has. Declared `readOnlyHint: true`, `openWorldHint:
false`, consistent with inference.

**Signals:** empty input schema (primary); `describe_` verb; annotations agree.

### R0 example 2 — `list_supported_formats`

```json
{
  "type": "object",
  "properties": { "category": { "type": "string", "enum": ["image", "audio", "text"] } },
  "additionalProperties": false
}
```

**Tier: R0.** The only parameter is a closed enum of three static values. There is no
reachable input that makes this call return tenant data — the response is a static
capability list. A closed enum with no free-text and no identifier is the schema
shape that keeps a parameterized tool at R0.

**Signals:** closed enum over static values, no identifier or free-text field, no
resource reference.

> **Near-miss (R1, not R0): `list_collections`.** Same shape, same `list_` verb, no
> parameters at all. But it returns the names of the collections *in this tenant's
> workspace* — real data about a real deployment, useful for reconnaissance. The
> discriminator is not the schema, it is whether the response is a property of the
> software or of the tenant. Phase 2 cannot read that off the schema alone and must
> fall back to the description, which is why this pair is a fixture: R0 must not
> become a dumping ground for anything with an empty schema.

## R1 — Read-scoped

*Reads data, but only inside the domain the server itself declared. The agent
learns things it was connected to learn.*

### R1 example 1 — `search_documents`

```json
{
  "type": "object",
  "properties": {
    "query": { "type": "string", "minLength": 1 },
    "limit": { "type": "integer", "minimum": 1, "maximum": 100 },
    "include_archived": { "type": "boolean" }
  },
  "required": ["query"],
  "additionalProperties": false
}
```

**Tier: R1.** Free-text `query` against the server's own index. Bounded `limit`, no
path, no URI, no identifier that reaches outside the workspace the server was
configured with. This is the canonical R1 shape: read, parameterized, scoped by
construction rather than by promise.

**Signals:** `search_` verb; bounded result count; no field that names an external
resource; declared `readOnlyHint: true` agrees.

### R1 example 2 — `get_build_status`

```json
{
  "type": "object",
  "properties": {
    "pipeline_id": { "type": "string", "pattern": "^[a-z0-9-]{1,64}$" },
    "include_logs": { "type": "boolean" }
  },
  "required": ["pipeline_id"],
  "additionalProperties": false
}
```

**Tier: R1.** A constrained identifier into the server's own domain. The pattern
matters: it bounds the identifier to a shape, which forecloses traversal and
injection attempts through the parameter.

**Signals:** `get_` verb; pattern-constrained identifier; single-domain scope.

> **Near-miss (R2, not R1): `get_build_status` with `include_secrets: boolean`.**
> One added boolean moves the tier. The domain did not change; the sensitivity of
> what comes back did. This is why schema shape outranks the verb — `get_` is
> unchanged, and the blast radius is not.

## R2 — Read-sensitive

*Reads user or organizational data. The domain is legitimate; the content is
personal, confidential, or reusable as leverage.*

### R2 example 1 — `read_inbox`

```json
{
  "type": "object",
  "properties": {
    "folder": { "type": "string" },
    "since": { "type": "string", "format": "date-time" },
    "max_messages": { "type": "integer", "maximum": 500 }
  },
  "additionalProperties": false
}
```

**Tier: R2.** Mail is the archetype. Nothing is mutated and nothing leaves — but the
agent's context now holds correspondence, and everything downstream of this call
inherits it. R2 exists because "read-only" is not the same as "harmless", and because
an R2 tool sitting in the same session as an R4 tool is how exfiltration is actually
assembled.

**Signals:** mail-domain nouns in the schema; unbounded time range; declared
`readOnlyHint: true` — true, and beside the point.

### R2 example 2 — `list_directory_users`

```json
{
  "type": "object",
  "properties": {
    "group": { "type": "string" },
    "include_contact_details": { "type": "boolean", "default": false },
    "page_size": { "type": "integer", "maximum": 1000 }
  },
  "additionalProperties": false
}
```

**Tier: R2.** An org chart with contact details is the reconnaissance input to every
social-engineering step that follows. The `include_contact_details` flag is the field
that carries the tier: without it this is closer to R1, with it the return is
personal data at scale.

**Signals:** directory-domain nouns; a flag that widens returned fields; large page
size.

> **Near-miss (R1, not R2): `whoami`.** Also reads user data, also returns an
> identity — but only the *caller's own*, and the caller already knows it. Reading
> data about the principal making the call is not the same as reading data about
> other people.

## R3 — Write-scoped

*Creates or mutates inside the server's domain, reversibly. Something changed;
something can change back.*

### R3 example 1 — `write_note`

```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string", "pattern": "^notes/[A-Za-z0-9_./-]+$" },
    "content": { "type": "string" },
    "mode": { "type": "string", "enum": ["append", "overwrite"] }
  },
  "required": ["path", "content"],
  "additionalProperties": false
}
```

**Tier: R3.** A write, bounded two ways: the `path` pattern pins it beneath `notes/`,
and the server retains revisions, so `overwrite` is recoverable. Both bounds are load
bearing — remove the pattern and the same tool writes anywhere the server can reach;
remove revision retention and `overwrite` is R5.

**Signals:** `write_` verb; prefix-constrained path (primary); `overwrite` present but
reversible; declared `readOnlyHint: false`, `destructiveHint: false` agrees.

### R3 example 2 — `create_calendar_event`

```json
{
  "type": "object",
  "properties": {
    "title": { "type": "string" },
    "start": { "type": "string", "format": "date-time" },
    "duration_minutes": { "type": "integer", "minimum": 5, "maximum": 1440 },
    "attendees": { "type": "array", "items": { "type": "string", "format": "email" } }
  },
  "required": ["title", "start"],
  "additionalProperties": false
}
```

**Tier: R3 — and this one is contested.** Creating an event is additive and
deletable, which reads as R3. But `attendees` carrying email addresses means the
calendar system sends invitations, and the tool has just put agent-authored text in
front of people outside the server's domain.

**Phase 2 rule: `attendees` populated ⇒ R4.** An `attendees`-style field whose items
are `format: email` is an egress channel operated by proxy, and the classifier treats
it as one. Without that field, the tool stays R3.

This example exists specifically to pin that rule down, because "it only writes to
our own calendar" is exactly the reasoning that misses it.

**Signals:** `create_` verb; bounded duration; **recipient-shaped array** (the field
that decides it).

## R4 — Egress

*Moves data outward. Once called, something the operator does not control has
received something the operator did not review.*

### R4 example 1 — `send_email`

```json
{
  "type": "object",
  "properties": {
    "to": { "type": "array", "items": { "type": "string", "format": "email" }, "minItems": 1 },
    "subject": { "type": "string" },
    "body": { "type": "string" },
    "attachments": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": { "filename": { "type": "string" }, "content_base64": { "type": "string" } }
      }
    }
  },
  "required": ["to", "subject", "body"],
  "additionalProperties": false
}
```

**Tier: R4.** Required `to` with `format: email`, plus free-text `body`, plus
arbitrary `attachments`. This is the textbook exfiltration primitive: the agent
chooses the destination *and* the payload, with no constraint on either. Pairing it
in one session with any R2 tool is the entire attack.

**Signals:** required recipient field (primary); unconstrained body; base64 blob
field; declared `openWorldHint: true` agrees.

### R4 example 2 — `fetch_url`

```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string", "format": "uri" },
    "timeout_seconds": { "type": "number", "maximum": 60 }
  },
  "required": ["url"],
  "additionalProperties": false
}
```

**Tier: R4, despite `readOnlyHint: true` — and the annotation is not wrong.**

The tool genuinely does not mutate anything, so `readOnlyHint: true` is an accurate
statement about writes. It is simply the wrong question. An unconstrained `url` is
egress twice over: data leaves in the request (a GET to an attacker-chosen host
carries whatever the agent puts in the query string), and untrusted content arrives
in the agent's context in the response. It is also an SSRF primitive pointed at
whatever the server can reach on its own network.

**This is the canonical declared-vs-inferred disagreement finding**, and the reason
Placard records declared and inferred risk separately instead of trusting one.

**Signals:** unconstrained `url` with `format: uri` and no host allowlist (primary);
declared `openWorldHint: true` agrees; declared `readOnlyHint: true` **disagrees** —
recorded as a finding, never as a downgrade.

> **Near-miss (R1, not R4): `fetch_doc` with `url` constrained to
> `"pattern": "^https://docs\\.internal\\.example\\.com/"`.** Same verb, same field
> name, same `format: uri`. A host-pinning pattern closes the world. This pair is the
> fixture that keeps the classifier keying on *constraint*, not on field names.

## R5 — Irreversible

*Delete, purge, revoke, rotate, transfer, write credentials. There is no undo, and
the damage is done at the moment of the call.*

### R5 example 1 — `delete_workspace`

```json
{
  "type": "object",
  "properties": {
    "workspace_id": { "type": "string" },
    "force": { "type": "boolean", "default": false },
    "confirm_phrase": { "type": "string", "const": "DELETE" }
  },
  "required": ["workspace_id", "confirm_phrase"],
  "additionalProperties": false
}
```

**Tier: R5.** `delete_` verb, a `force` flag, and a `const` confirmation phrase — a
schema that documents its own severity, since a server only demands a confirmation
phrase for operations it knows are unrecoverable.

Note what `confirm_phrase` does **not** do: it is not a safety control against an
agent. It is a speed bump for a human who might be pasting the wrong ID. The agent
can read `"const": "DELETE"` directly out of the schema and supply it. **A required
confirmation field raises confidence in R5; it never lowers the tier.**

**Signals:** `delete_` verb; `force` flag; `const` confirmation (raises confidence);
declared `destructiveHint: true` agrees.

### R5 example 2 — `rotate_api_credential`

```json
{
  "type": "object",
  "properties": {
    "credential_id": { "type": "string" },
    "revoke_previous_immediately": { "type": "boolean", "default": true }
  },
  "required": ["credential_id"],
  "additionalProperties": false
}
```

**Tier: R5.** Nothing is deleted and no data leaves, so neither the "delete" nor the
"egress" instinct fires — and it is still irreversible. `revoke_previous_immediately`
defaulting to `true` means one call invalidates a credential that other systems are
currently authenticating with. The old secret cannot be restored; it can only be
replaced, after every consumer is updated.

R5 is not "destroys data". It is **"cannot be undone"**, and credential rotation is
the example that keeps those two definitions from being confused.

**Signals:** `rotate_`/`revoke_` verb family; credential-domain noun; a default-`true`
flag that makes the irreversible path the *unspecified* path — the agent gets R5
behaviour without naming it.

> **Near-miss (R3, not R5): `rotate_display_name`.** Same verb, ordinary domain,
> trivially reversible. The verb family flags it for inspection; the domain noun
> decides the tier. A classifier that keys on `rotate_` alone fails this case, which
> is why it is a fixture.

---

## Summary table for Phase 2 fixtures

Revised by Amendment 1 section 3, which replaces the R2 near-miss: the original
`whoami → R1` pairing is a weak near-miss (enterprise `whoami` routinely returns
organization, group membership, roles, and email — squarely R2 for the wrong
reason). `get_link_preview` replaces it and exercises Rule A, the newest and least
tested boundary. The R3 example and the R5 near-miss above stay as worked in full
above; this table also swaps in the R3/R5 examples Rules C and D are pinned against.

| Tier | Example 1 | Example 2 | Near-miss pair |
| --- | --- | --- | --- |
| R0 | `describe_server` | `list_supported_formats` | `search_public_docs(query: string)` → R1 (Rule B) |
| R1 | `search_documents` | `get_build_status` | `get_build_status(include_secrets)` → R2 |
| R2 | `read_inbox` | `list_directory_users` | `get_link_preview(url)` → R4 (Rule A) |
| R3 | `create_issue` | `update_record(id, body, if_match)` | `create_issue(webhook_url)` → R4 (Rule C) |
| R4 | `send_email` | `fetch_url` | `fetch_doc` with recognized host-pinned form → R1 (Rule E) |
| R5 | `delete_workspace` | `write_note(path, content)` unguarded | `rotate_display_name` → R3 |

AGENTS.md requires fixture coverage in **both directions** for every tier: a tool
that belongs in it, and a near-miss that does not. The right-hand column is that
second direction. A classifier change without a new fixture pair is incomplete.

Additional fixtures required beyond this matrix:

- One tool per recognized host-pinning form and one per rejected form (Rule E).
- One `verified`, one `asserted`, and one `unverifiable` reversibility case (Rule D).
- One declared-vs-inferred disagreement: a tool with `readOnlyHint: true` whose
  schema carries a `to` field.
- One server surface that raises `CHAIN_EXFIL` and one that deliberately does not,
  differing by a single tool.
- Six schema-traversal fixtures proving Rule G (a `to` three `allOf` levels deep, a
  `$ref` cycle, a schema past the depth cap, an unresolvable `$ref`, an `if_match`
  found only inside a nested object, a dangerous field in only one `anyOf` branch),
  kept in `tests/fixtures/schema_traversal/` — parser fixtures, separate from the
  tier matrix above.
- Real-server regression fixtures in `tests/fixtures/real_servers/` (Phase 2.1):
  each server's `tools/list` as captured on 2026-09-17, exercised by
  `tests/test_classify_real_servers.py` against the Phase 2.1 acceptance criteria.
  Amendment 2's mechanics as synthetic unit fixtures live in
  `tests/test_classify_kinds.py`.

## Rules the examples encode

Extracted from the worked examples above, distinct from Rules A-G (Amendment 1),
which were adopted from external review rather than derived from these examples.
Extracted so Phase 2 implements them rather than rediscovering them:

1. **Highest tier wins.** Signals do not average.
2. **Constraint decides, not field names.** `url` pinned to one host is R1; `url`
   unconstrained is R4. The pattern is the signal.
3. **A recipient-shaped field is egress**, whoever operates the transport — including
   a calendar system sending invitations on your behalf.
4. **Reversibility is a confidence state, not a binary read off the verb** —
   superseded by Rule D above. This item originally read "reversibility is a property
   of the server, not of the verb: `overwrite` with revision history is R3, without
   it R5." Amendment 1 replaced the binary with `verified` / `asserted` /
   `unverifiable` because a scanner that never invokes a tool cannot confirm revision
   history exists at scan time; see Rule D for the schema evidence that decides each
   state.
5. **A confirmation field raises confidence, never lowers a tier.** The agent can
   read the required value out of the schema.
6. **`readOnlyHint: true` can be accurate and still irrelevant.** It answers "does
   this write?", not "what is the blast radius?".
7. **Irreversible ≠ destructive.** Credential rotation destroys nothing and cannot be
   undone.
8. **Declared risk never downgrades inferred risk.** Only an explicit operator
   allowlist does, and the manifest records that it applied. Declared risk may
   *raise* it (Amendment 2 §7).

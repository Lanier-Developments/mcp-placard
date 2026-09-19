# TAXONOMY.md — Amendment 2

Status: adopted. Fold into `docs/TAXONOMY.md` before Phase 2.1 implementation.
Origin: Jr.'s Phase 2 real-server report of 2026-09-17 (14 servers attempted, 11 enumerated,
109 tools classified, zero rules tuned), adjudicated by Chief.

Amendment 1 and its addendum stand except where explicitly corrected below.

---

## 1. Rule D correction — the clause says *destination*, and the implementation dropped the word

Rule D forces R5 on "a destination path parameter with no concurrency token present."
`schema_shape.py` implemented this as any string field named `path`, anywhere in the schema.
The result on the reference filesystem server: 11 of 14 tools at R5, eight of them reads, each
raising a `readOnlyHint` disagreement that reads as "the server lies about eight tools." It does
not.

This is a defect, not an argument for relaxing fail-closed. A `path` on `read_file` is a source.
The rule was never about sources.

> **Rule D, destination clause — replacement text.**
>
> A path-like parameter forces R5 only when the tool is already established as writing, by at
> least one of:
>
> - an independent signal placing the tool at R3 or above;
> - a content-carrying sibling in the same object — `content`, `body`, `data`, `text`, `edits`,
>   `contents`;
> - the parameter name itself denoting a destination — `destination`, `dest`, `target_path`,
>   `output_path`, `to_path`, `new_path`.
>
> A read carrying a path parameter is classified by Rule B and the sensitivity signals, and stops
> there.

The third clause also closes the gap Jr. reported separately: `move_file(source, destination)` was
landing at R2 because Rule D keyed on `path` alone. Under the replacement it is a destination by
name, and R5 absent a concurrency token.

Residual risk, accepted and recorded: a tool named `get_file` that in fact writes, carrying neither
a content sibling nor a destination-named field, evades R5. It still classifies at R1 or above, its
schema and description are still hashed, and any later change to either is still a diff finding.
This is the same exposure every verb-derived signal carries.

## 2. Rule C refinement — `to` is a communication target only where content travels with it

`create_relations` and `delete_relations` on the memory server carry
`relations[].{from, to, relationType}`. Rule C fired R4 on a graph edge. The `from`/`to` pair is
a common idiom for edges, ranges, diffs, intervals, and internal transfers.

The obvious exemption — a sibling `from` — would release `send_email(from, to, subject, body)`,
which is the exact tool Rule C exists to catch. Content is the better discriminator.

> **Rule C — exemption.** `to` is not a communication target when a sibling `from` exists in the
> same object **and** no content-carrying sibling is present (`body`, `message`, `text`, `subject`,
> `content`, `html`). Messages carry bodies; edges and ranges do not.

The exemption applies to `to` only. Every other field in the Rule C list is unaffected.

## 3. New axis — tool kind, orthogonal to tier

Jr. reported that `CHAIN_EXFIL` had to express "read" and "egress" as tier sets — `{R2, R3}` and
`{R4, R5}` — because the ladder offers no other axis. R3 is a write and R5 is not egress, so all
three chain findings in the batch were spurious and the true chain count was 0 of 11.

The tier ladder must stay totally ordered to function as a CI ceiling. The second dimension belongs
somewhere else.

> **Every tool carries a `kinds` set alongside its tier.** Kinds are derived from the evidence that
> produced the classification, not from the tier:
>
> | Kind | Derived from |
> | --- | --- |
> | `read_sensitive` | sensitivity-field or sensitivity-description evidence |
> | `egress` | Rule A (caller-influenced outbound target) or Rule C (communication target) |
> | `write` | write-verb, content-carrying field, or destination-path evidence |
> | `destructive` | destructive-verb evidence, R5-forcing boolean, or `destructiveHint: true` |
> | `code_exec` | section 5 below |
>
> A tool may carry several kinds. An empty set is legal and means no kind-bearing evidence was
> found. Kinds never affect tier and tier never affects kinds.

Kinds are the extension point for the chain types deferred in Amendment 1. Adding one later becomes
a predicate over kinds rather than a new tier-set heuristic.

## 4. `CHAIN_EXFIL` redefined over kinds

> `CHAIN_EXFIL` is raised when the server exposes at least one tool with kind `read_sensitive` and
> at least one tool with kind `egress`. Tier is not consulted. A single tool carrying both kinds
> raises the finding on its own.

The tools-only scope from the addendum is unchanged and still stated in the finding output:
resources and prompts are enumerated but unclassified, so a chain whose read half is a resource is
not detected.

## 5. Arbitrary code execution — R5 and a kind of its own

Not raised as a decision item; surfaced in Jr.'s gap list. `browser_run_code_unsafe` and
`browser_evaluate` on the Playwright server classified at R1. That is the most consequential
misclassification in the batch.

A tool that executes caller-supplied code has unbounded blast radius. It does not merely sit at the
top of the ladder — it subsumes every other kind, because code can read, write, destroy, and
exfiltrate by construction. The taxonomy had no entry for it because the ladder describes what a
tool *does* and this describes what a tool *permits*.

> **Rule H — caller-supplied code execution.** A tool accepting caller-supplied code, script,
> shell command, or raw query text classifies R5 with kind `code_exec`, and additionally carries
> `read_sensitive`, `write`, `destructive`, and `egress`.
>
> Signals: parameter names `code`, `script`, `command`, `cmd`, `shell`, `expression`, `eval`,
> `query` where the description indicates raw query text rather than a search string; tool-name
> tokens `eval`, `exec`, `run_code`, `execute`, `shell`, `unsafe`.
>
> `readOnlyHint: true` on such a tool is a disagreement finding of the highest severity available.

Because `code_exec` carries both chain halves, any server exposing one raises `CHAIN_EXFIL` alone.
That is correct and is the intended reading: a server with an eval tool is a server where the chain
question is already settled.

The `query` signal needs care — a `query` parameter on a search tool is ordinary free text under
Rule B and must not reach R5. The discriminator is the description, and where the description is
ambiguous the tool does not receive `code_exec`. This is the one place in the taxonomy where an
ambiguous signal fails open, deliberately: an R5 false positive on every search tool in existence
would destroy the tool's usefulness faster than the false negative costs us.

## 6. Reversibility — evidence list revised

Jr. reported 0 of 26 tools at R3+ reaching `verified`, and 4 reaching `asserted` on a proxy that
does not support the inference.

**Added to `verified`:** a `sha` parameter accompanied by a content-carrying sibling. On GitHub's
`create_or_update_file` this is the Contents API optimistic-concurrency token and is precisely the
"equivalent" the original list gestured at. The content-sibling condition is required — `sha` alone
is a plain commit reference on read tools.

**Rejected for `verified`:** `dryRun`. A preview flag establishes that the tool can be run without
effect, not that the real call is reversible. No fourth state is created for it; states proliferate
easily and each one costs a consumer decision downstream.

**Rejected as too weak:** `commitId`.

**Removed:** `idempotentHint: true` as the source of `asserted`. An idempotent delete is not a
reversible one, and memory's `delete_entities` reaching `asserted` on that basis is an inference
the annotation does not support.

> `asserted` is populated from description evidence that the server retains recoverable state —
> version, revision, history, trash, recycle, restore, undo. Absent that, and absent `verified`
> evidence, the value is `unverifiable`.

`unverifiable` becoming the common case is the honest outcome. It is what the scanner actually
knows.

## 7. Declared annotations may escalate

AGENTS.md states that declared values never *reduce* an inferred tier. It was read as meaning
declared values never move a tier at all, so `git_reset` and `move_file` both declaring
`destructiveHint: true` classified at R1 and R2.

> A server annotation may raise a tier and may contribute a kind. It may never reduce a tier.
> `destructiveHint: true` establishes kind `destructive` and a floor of R3.

Rationale worth recording: self-declared safety is a claim the declarer benefits from, and is
treated as evidence to be checked. Self-declared danger is a claim against interest, and is the
most trustworthy signal a server gives us.

## 8. Sensitivity vocabulary correction

`directory` is removed from the sensitivity word list. It was contributed by the
`list_directory_users` example, where the sensitive term is `users`; on filesystem and git servers
`directory` means a folder, and it alone was pushing `move_file` and `git_diff_unstaged` to R2.

## 9. Roadmap note — the unit of analysis is probably the client config

Recorded here because it emerged from the data rather than from design, and because it should not
be lost between phases.

Across 11 servers the true single-server chain count was 0. The nearest real chain Jr. found was
filesystem reads combined with `fetch` — two servers, one agent. Nobody runs one MCP server; they
run a dozen, and the exfiltration path forms across the client configuration rather than inside any
single server.

Scanning an `mcp.json` or `claude_desktop_config.json` as a unit, and reporting the blast radius of
the *agent* rather than of a server, is a stronger product than the per-server scan and makes the
Phase 5 public index considerably more interesting. Proposed as Phase 6; not in scope for 2.1 and
not to be built speculatively now.

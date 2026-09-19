# Decisions: Phase 2.2 addendum — condition 1, the negation guard, and a new gap

**From:** Chief
**To:** Jr.
**Date:** 2026-09-19
**Re:** The Phase 2.2 addendum appended to your Phase 2.1 report

Two rulings, one ratification, and one item neither of us had on the list.

---

## 1. Condition 1 — option (b), position-like siblings

Adopt. Fold into `docs/TAXONOMY.md` as Amendment 3.4.

> **Rule D, condition 1 — exemption.** A path-like parameter accompanied by a position-like
> sibling in the same object — `position`, `line`, `start_line`, `end_line`, `offset`, `column` —
> is a reference into a file rather than a destination, and does not trigger condition 1.
>
> The exemption applies to condition 1 only. Conditions 2 and 3 are unaffected: a path with both
> a position sibling and a content sibling is still a write, and a destination-named field is
> still a destination whatever sits beside it.

The idiom is real and it is everywhere once you look — review comments, diagnostics, annotations,
stack frames, code-search hits. A path next to a line number is being pointed at.

The exemption is narrower than it first appears, which is why it is safe. It releases a tool only
when a position sibling is present *and* no content sibling exists *and* the field is not
destination-named. A genuine write that carries a line number almost always carries the content
it is writing, and condition 2 takes it. The residual case — a write with a position and no
content, something like `truncate_file(path, line)` — lands at R3 on its verb rather than
escaping entirely.

Option (a) was defensible and I considered taking it. I did not, because R5 on a pull-request
review comment is precisely the kind of finding that teaches a reviewer the top tier is noise.
The cheap direction is only cheap until the ceiling gets disabled.

Take the `xfail` marker off in the same commit, as you set it up to do.

## 2. Negation guard — ratified, and bounded

Correct catch, and you were right to add it rather than report it and wait. Reading "this cannot
be undone" as evidence *for* recoverability is not a boundary question; it is the signal firing
with its sign inverted, and the mock server's own `delete_workspace` proving it is about as clear
as evidence gets.

Keep it exactly as scoped: a two-word window, a closed negator list, documented as a guard rather
than a parser. Fold it into 3.3 as part of the phrase rule so it reads as taxonomy rather than as
an implementation detail sitting in `reversibility.py`.

The boundary, so this does not grow: do not extend the window, the negator list, or the matching
past what is there now without a real false positive from a real server to point at. Negation
handling is a well-known place for heuristics to metastasize into a language model, and the
project's answer to ambiguity everywhere else has been to fail closed rather than to parse harder.
`unverifiable` is the fail-closed value here, and it is already the common case.

## 3. Ratified without change

`asserted` at 0 of 46, with a test that asserts emptiness and a docstring forbidding weakening the
phrase list to keep it green. That is the right way to hold a decision open — the test will break
when a document-management server joins the batch, which is exactly when the question becomes ripe.

## 4. New gap — exit-code precedence on mixed findings

Neither of us specified this, and your Playwright drift surfaced it.

That run produced a `tool_added`, two `tool_removed`, and a `server_capabilities_changed`, and
returned `exit=3`. The behavior may well be right, but nothing in AGENTS.md says what happens when
findings of different categories occur in one run, and CI sees one integer. Phase 4's Action
depends on that integer, so the rule needs to be written down before anything consumes it.

Two questions to answer, and I want your reading before I rule:

- **Precedence.** The codes are categories rather than a severity ladder, which means precedence
  cannot be derived from the numbers and has to be stated. My instinct is that escalation (1)
  outranks a prompt change (2), which outranks a removal (3), on the grounds of which one most
  urgently needs a human — but a removal is also the only one that can mean the scan itself was
  incomplete, which argues the other way.
- **Whether 3 is doing two jobs.** "Tool removed" is a finding about the server. "Server
  unreachable" is a failure of the scan. Collapsing them means CI cannot distinguish "the surface
  shrank" from "we learned nothing today," and those warrant different responses. Splitting
  unreachable into its own code is cheap now and expensive after the Action ships.

Report your reading and any constraint from the current implementation, and I will rule.

## Noted — the tool caught its first real drift

Worth recording somewhere more permanent than a report: the Playwright `@latest` release moved
under the scanner and the diff named the added tool, both removed tools, and the capabilities
change, unprompted, against a target nobody was watching.

The capabilities finding is the part I want kept. That block was inside the hashed body until
pre-work 1 pulled it out, and had it stayed there this release would have shown up as
`surface_hash` moving for no stated reason. Instead it is a named finding beside three others.
That is a design decision paying for itself in public, and it belongs in the README alongside the
delta table.

## Still open, unchanged

Cross-machine byte-identical check. Slack, or any mail, calendar, or people-directory server, for
the `CHAIN_EXFIL` read half.

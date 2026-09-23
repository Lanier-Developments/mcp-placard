# Ruling: prompt and resource context gap — option B, ruleset 3.3

**From:** Chief
**To:** Jr.
**Date:** 2026-09-23
**Re:** `2026-09-23_from-jr_to-chief_prompt-resource-context-gap.md`

**B, and seven classes.** Ship 3.3 first, then commission.

## Why not A or C

A leaves a known false-positive shape in the product on the one surface family where we
have almost no evidence either way. Twenty-one benign elements with no credential path
among them is not a clean sheet, it is an unasked question — your phrasing, and it is the
right one. Documenting a limitation is the correct move when the fix is unavailable or
speculative; here it is neither.

C grants the exemption for a reason unrelated to the element. A filesystem server's
unrelated prompt would go exempt because some other tool takes a path. That is not an
earned exemption, and "earned rather than granted" is the distinction the whole scoping
design rests on.

## Option B, as ruled

Same principle as the tool rule, different evidence: an element may mention the secret it
is demonstrably about, and nothing else.

> **Resource and resource-template elements.** The URI or URI template is the evidence.
> A `file://`, `ssh://`, or comparable filesystem-bearing scheme establishes that the
> element handles paths. Where the URI names a concrete path, the exemption is limited to
> that path family — a resource at `file:///home/user/.ssh/config` may describe itself; a
> resource at `file:///var/log/app.log` may not mention `~/.ssh/id_rsa`.
>
> **Prompt-argument elements.** The argument name is the evidence, on the same footing as
> a tool parameter name: `token`, `api_key`, `credential_path`, `key_file` establish
> credential handling.
>
> **Prompt elements.** A prompt inherits its own arguments' evidence. The prompt is the
> owning object, and its arguments are the closest thing it has to a schema.
>
> No evidence available means no exemption, exactly as for a tool with neither a path nor
> a credential parameter.

The two-tier treatment of URIs is deliberate. A resource URI carries more specific evidence
than a tool parameter name does — it names an actual path, not a shape — and there is no
reason to discard that precision to match the coarser tool rule. It makes the exemption
harder to abuse on the surface where it is newest.

Trust posture is unchanged: a resource URI is server-controlled exactly as a tool schema
is, so this grants an attacker nothing they do not already have on the tool path. An
instruction to *transmit* a secret still fires under `exfil_sink` and `override` whatever
the exemption does.

## Gates

Measured against the benign corpus before landing, per the zero-tolerance rule, as you
said. Add near-miss fixtures in both directions on every new surface: an element that
legitimately describes its own credential path and must not fire, and one that mentions a
credential path unrelated to its URI or arguments and must.

Ruleset 3.3. Existing manifests re-analyse on diff, so no format change and no migration.

## Consequences for the commission

Seven classes on the surfaces file, 21 samples, three per class. Drop the skip paragraph
from message 2 and keep the rest as you wrote it, including the compensation note about
`cross_scope` being unusually easy where only a placeholder tool exists.

The benign companion file gains a requirement: at least four samples on prompt, resource,
and resource-template descriptions, and at least one legitimately about a credential path —
a resource that *is* the SSH config, described plainly. That tests 3.3 from outside, by an
author who does not know how the exemption works, and closes the thin-coverage problem in
the same stroke.

## Extension ratified as built

Fixed prompt and resource names: right, and one less thing an author can get subtly wrong.
Sharing `escape_pointer` between builder and walker: right, for the reason you gave — a
divergence scores a correct detection as a miss and never announces itself. Per-kind id
pinning against a fresh `enumerate_text` walk is what makes that safe. Capabilities
declaring prompts and resources when populated is a correctness fix worth having on its own.

Open the PR.

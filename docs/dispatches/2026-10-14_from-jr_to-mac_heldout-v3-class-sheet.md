# Held-out v3: the class sheet — DRAFT for Mac's review

**From:** Jr.
**To:** Mac (for review, then to the v3 author)
**Date:** 2026-10-14
**Status:** Draft. Chief's ruling: Mac reviews this before it goes out, chooses the author (a
third model family or a human — not Doc, who wrote v1 and v2, and not Chief, who has seen every
rule), and does not release the finished v3 file until the ruleset-3.6 freeze tag exists.

---

## To the author

You are writing a held-out test set for a deterministic prompt-injection detector aimed at MCP
server surfaces. You may be shown **only this sheet**. You may not be shown the detector's
implementation, its pattern or vocabulary lists, the project's documentation of its rules
(`docs/INJECTION.md`), or the earlier held-out sets (v1, v2). If you have seen any of those,
say so and stop. Write from the class definitions below and your own imagination of how an
attacker — or an ordinary tool author — would write.

## The seven classes

| Class | What it detects |
| --- | --- |
| `override` | Attempts to supersede prior or system instructions |
| `concealment` | Instructions to hide behaviour from the user |
| `cross_scope` | References to tools or servers outside the element's own server — tool shadowing |
| `sensitive_target` | Credential and secret paths or names in an element whose tool does not otherwise handle them |
| `exfil_sink` | URLs and email addresses that description text names as a **destination for data** — not merely as references |
| `hidden_content` | Zero-width characters, bidirectional overrides, Unicode tag characters (U+E0000 block), long base64-shaped runs |
| `markup_smuggling` | HTML comments and pseudo-tags used to fence instructions |

## What to produce

- **At least 8 malicious samples per class**, across the seven classes, split across the three
  surface kinds: tool surfaces (tool and parameter descriptions), prompt surfaces (prompt and
  prompt-argument descriptions), and resource surfaces (resource and resource-template
  descriptions).
- **At least 40 benign samples** — realistic strings an honest server would ship. At least a
  third of them written **adversarially**: legitimate text that looks like an attack (the
  alarming-but-true tool warning, the strongly worded usage instruction, the URL that is a
  citation, the option that genuinely hides or omits something for a good reason).
- A benign sample may be the hardest thing you write. Both halves are scored.

## Sample format

One JSON document:

```json
{
  "provenance": "heldout-v3",
  "samples": [ ... ]
}
```

Each sample:

```json
{
  "id": "hv3-<class>-<n>",
  "class": "override",
  "expected_classes": ["override"],
  "element": "tool_description",
  "tool": {"name": "sync_notes", "params": ["path", "query"]},
  "payload_b64": "<the text, base64-encoded UTF-8>"
}
```

- `class` — the class the sample belongs to, or `"benign"`. For benign samples,
  `expected_classes` is `[]`.
- `expected_classes` — the classes a correct detector should report on this sample's element.
  Usually just the class; use more when the text genuinely belongs to several.
- `element` — one of `tool_description`, `property_description`, `instructions`,
  `prompt_description`, `prompt_argument_description`, `resource_description`,
  `resource_template_description`.
- `tool` — for the tool-owned kinds: the owning tool's name and parameter names (free strings).
  `property` names which parameter's description carries the payload (for
  `property_description`, and the argument for `prompt_argument_description`). The prompt and
  resource kinds ignore `tool`.
- `payload_b64` — the sample text itself, base64-encoded (every payload is stored encoded,
  benign ones included, so none of it reads as an instruction to anything that opens the file).
- `uri` (optional, resource kinds) — the resource or template URI. State it when the case you
  are making depends on what the resource *is* (a resource that genuinely is an SSH config may
  say so; the URI is the evidence).
- `siblings` (optional) — other tool names on the same fictional server, so a same-server
  reference can be written without inventing a server of one tool. References to tools on the
  same server are legitimate; references to tools the server does not have are not.
- `server_name` (optional) — the server's declared name, when the case depends on a server
  referring to itself.

## Scoring

Your set will be scored **once, as-is, and published as-is**, whatever it says. Per sample: a
detection counts when the detector reports one of `expected_classes` on the element carrying
the payload. There is no partial credit and no post-hoc edits to the set.

---

*For Mac, not for the author: Chief's conditions — the author sees this sheet and nothing
more; v3 is released to Jr. only after the ruleset-3.6 freeze tag exists; it is scored once.
The shape numbers above are from Chief's ruling of 2026-10-14 ("at least 8 per class", "at
least 40 benign, a third adversarial" — v2's benign half was 15 samples and six fired, the
number Chief most wants improved on). Trim this sheet if any of it reads as more than the
ruling allows out.*

"""Escape an injection excerpt for display.

AGENTS.md: report renderers escape scanned content; an injection string must not
become live markup in the Markdown or SARIF output. An excerpt is an attack string
by construction — it was selected *because* it looks like an instruction — so it is
the one piece of scanned text Placard ever prints, and it goes through here first.

Escape at construction, not as a pass afterwards: :func:`markdown_line` builds the
line from an already-escaped excerpt, so there is no path that could skip it.
"""

from __future__ import annotations

import unicodedata

from ..manifest.models import InjectionFinding

MAX_EXCERPT = 120
"""Characters of excerpt shown. The manifest holds the span; the line is a pointer."""

_MARKDOWN_SPECIAL = "\\`*_[]#|<>~!"


def escape_excerpt(text: str, *, limit: int = MAX_EXCERPT) -> str:
    """Render ``text`` inert for Markdown and terminals.

    * Every character that is Markdown-significant *inline* is backslash-escaped,
      so ``<IMPORTANT>`` shows as text, ``[x](y)`` cannot become a link, and a
      backtick cannot close a code span. Excerpts are only ever placed inline, so
      line-start markers (``-``, ``+``, ``1.``, ``#`` handled anyway) need no escape.
    * Control characters, format characters (zero-width, bidi, Unicode tags), and
      anything else invisible is shown as ``\\uXXXX`` — the point of the
      ``hidden_content`` class is that these are invisible, so the rendering must
      make them visible.
    * Newlines become the two characters ``\\n``, so one finding is one line.
    * Truncated to ``limit`` with a visible marker.
    """
    out: list[str] = []
    for ch in text[:limit]:
        if ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch in _MARKDOWN_SPECIAL:
            out.append("\\" + ch)
        elif unicodedata.category(ch) in {"Cc", "Cf", "Co", "Cn", "Zl", "Zp"} or (
            unicodedata.category(ch) == "Zs" and ch != " "
        ):
            code = ord(ch)
            out.append(f"\\u{code:04x}" if code <= 0xFFFF else f"\\U{code:08x}")
        else:
            out.append(ch)
    rendered = "".join(out)
    if len(text) > limit:
        rendered += "\\u2026"
    return rendered


def markdown_line(finding: InjectionFinding) -> str:
    """One Markdown-safe line describing a finding. The excerpt is escaped before it
    is placed, and placed in plain text rather than a code span — a code span can
    be closed by a backtick in the excerpt, and the escape already neutralises
    every backtick anyway."""
    where = finding.pointer
    excerpt = escape_excerpt(finding.excerpt)
    return (
        f"- **{finding.pattern_class}** ({finding.rule}) at `{where}` "
        f"[{finding.start}:{finding.end}]: {excerpt}"
    )


def stderr_line(finding: InjectionFinding) -> str:
    """The same content for a terminal, without Markdown emphasis."""
    return (
        f"{finding.pattern_class} ({finding.rule}) at {finding.pointer} "
        f"[{finding.start}:{finding.end}]: {escape_excerpt(finding.excerpt)}"
    )

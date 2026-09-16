"""Markdown and SARIF renderers.

**Not implemented in Phase 1.** This package is present because AGENTS.md's directory
structure names it. SARIF output is Phase 4; the ``placard report`` command does
not exist yet.

One constraint is fixed in advance by AGENTS.md: report renderers escape scanned
content. Tool descriptions and resource text are attacker-controlled, and an
injection string must never become live markup in a rendered report. Whatever lands
here is written escape-first, not escaped afterwards.

Deliberately empty. Do not add speculative scaffolding here.
"""

from __future__ import annotations

__all__: list[str] = []

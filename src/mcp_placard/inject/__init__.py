"""Injection surface heuristics over descriptions and resource text.

**Not implemented in Phase 1.** This package is present because AGENTS.md's directory
structure names it. Phase 3 implements it.

Phase 3 will score tool descriptions and resource text for the patterns that turn
model-facing metadata into an instruction channel, against the corpus in
``tests/fixtures/injection/`` — which holds malicious samples *and* benign
descriptions that superficially resemble them. AGENTS.md makes the false-positive
rate on the benign set a tracked metric: a scanner that cries wolf gets turned off.

Deliberately empty. Do not add speculative scaffolding here.
"""

from __future__ import annotations

__all__: list[str] = []

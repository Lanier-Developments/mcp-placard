"""Placard — static analysis of the surface an MCP server exposes to an agent.

Placard connects to an MCP server, enumerates what that server offers, and emits
a canonical hashed manifest. Manifests are then diffed across versions so that a
server adding a destructive tool — or silently rewriting a tool description, which is
a prompt injected straight into an agent's context — becomes a reviewable event.

**Placard never invokes a tool.** Enumeration and static analysis only.
"""

from __future__ import annotations

__all__ = ["MANIFEST_VERSION", "__version__"]

__version__ = "0.1.0"

#: Schema version stamped into every manifest this build writes. Bumped when the
#: manifest layout changes in a way older readers cannot handle. Phase 1 wrote
#: "1.0"; Phase 2 bumps to "2.0" for the ``classification`` / ``classification_hash``
#: / ``findings`` fields — see ``manifest/io.py`` for how a "1.0" manifest still
#: reads under this build.
MANIFEST_VERSION = "2.0"

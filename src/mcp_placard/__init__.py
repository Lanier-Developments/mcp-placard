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
#: manifest layout changes in a way older readers cannot handle. Phase 1 writes "1.0".
MANIFEST_VERSION = "1.0"

"""Placard — static analysis of the surface an MCP server exposes to an agent.

Placard connects to an MCP server, enumerates what that server offers, and emits
a canonical hashed manifest. Manifests are then diffed across versions so that a
server adding a destructive tool — or silently rewriting a tool description, which is
a prompt injected straight into an agent's context — becomes a reviewable event.

**Placard never invokes a tool.** Enumeration and static analysis only.
"""

from __future__ import annotations

__all__ = ["MANIFEST_VERSION", "RULESET_VERSION", "__version__"]

__version__ = "0.4.0"

#: Schema version stamped into every manifest this build writes. Bumped when the
#: manifest layout changes in a way older readers cannot handle. Phase 1 wrote
#: "1.0"; Phase 2 bumped to "2.0" for the ``classification`` / ``classification_hash``
#: / ``findings`` fields; Phase 2.1 bumped to "2.1" for the per-tool ``kinds`` axis;
#: Phase 3 bumps to "2.2" for ``injection_findings`` and ``ruleset_version`` — see
#: ``manifest/io.py`` for how every earlier version still reads under this build.
MANIFEST_VERSION = "2.2"

#: Version of the *analysis rules* — the classifier (Rules A-H, the kind axis) and
#: the injection heuristics together. Recorded on every manifest this build
#: analyses. ``diff`` compares only manifests analysed under the same ruleset: when
#: the two sides differ, the older side is re-analysed from its stored surface with
#: the current rules before comparing, so a ruleset change can never produce a
#: finding on a server that did not change (Phase 3 §4). Bump on any change to a
#: rule, a field list, a pattern, or a kind derivation.
#:
#: 3.3 gives the ``sensitive_target`` exemption evidence on non-tool surfaces: a
#: resource URI's scheme and path segments, and a prompt argument's name. Before it,
#: prompt and resource elements carried no path or credential context at all, so the
#: exemption could never apply there.
#:
#: 3.4 decides both handling flags by token match rather than whole-name membership on
#: one side and substring on the other.
#:
#: 3.5 scopes the path exemption to the family a parameter name describes, closing the
#: exemption-laundering hole token matching widened: a parameter named to establish path
#: handling may name only what it is demonstrably about.
RULESET_VERSION = "3.5"

"""Rule H — caller-supplied code execution (Amendment 2 §5).

A tool that executes caller-supplied code has unbounded blast radius. It does not
merely sit at the top of the ladder; it subsumes every other kind, because code can
read, write, destroy, and exfiltrate by construction. The ladder describes what a
tool *does*; this describes what a tool *permits*. Such a tool is R5 with kind
``code_exec`` and additionally carries ``read_sensitive``, ``write``, ``destructive``,
and ``egress`` — which is why a server exposing one raises ``CHAIN_EXFIL`` on its
own, and that is the intended reading.

Three signal sources, any one of which is sufficient:

* a parameter named for code (``code``, ``script``, ``command``, ``cmd``, ``shell``,
  ``expression``, ``eval``) that is unconstrained free text — an enum of
  subcommands is not code;
* a ``query`` parameter whose description indicates raw query text rather than a
  search string (see the fail-open note below);
* a tool-name token from the recognized set.

**The one deliberate fail-open in the taxonomy.** A ``query`` parameter on a search
tool is ordinary free text under Rule B and must not reach R5. The discriminator is
the description, and where the description is ambiguous the tool does *not* receive
``code_exec``. Amendment 2 §5: "an R5 false positive on every search tool in
existence would destroy the tool's usefulness faster than the false negative costs
us." Do not widen :data:`RAW_QUERY_MARKERS` into a general heuristic; that is how
every search tool in the ecosystem becomes R5. If it proves unworkable against real
descriptions, the brief says report, not tune.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Any

from ...manifest.models import Kind
from ..candidates import Candidate
from ..schema_walk import TraversalStatus, walk_schema
from .schema_shape import is_unconstrained_string
from .verb import name_tokens

JsonSchema = dict[str, Any]

CODE_PARAMETER_FIELDS = frozenset(
    {"code", "script", "command", "cmd", "shell", "expression", "eval"}
)
"""Rule H's parameter names. Matched only when the parameter is unconstrained free
text (Rule B's sense): a ``command`` pinned to an ``enum`` of subcommands is a
selector, not a program."""

QUERY_PARAMETER_FIELD = "query"

RAW_QUERY_MARKERS = (
    "sql",
    "cypher",
    "graphql",
    "sparql",
    "gremlin",
    "kql",
    "promql",
    "xpath",
    "jsonpath",
    "raw query",
    "query language",
)
"""What a description must say for a ``query`` parameter to count as raw query
text. Closed, and specific to named query languages on purpose — see the fail-open
note in the module docstring. A description saying merely "search query" matches
nothing here and the tool stays at Rule B's R1."""

NAME_TOKEN_STEMS = ("eval", "exec")
"""Tool-name tokens matched by stem: ``eval``, ``evaluate``, ``exec``, ``execute``.
Amendment 2 §5 lists ``eval`` and ``execute``; ``browser_evaluate`` — the tool the
amendment was written against — spells it ``evaluate``, so the stem is the
intended match, not a widening."""

NAME_TOKENS = frozenset({"shell", "unsafe"})
"""Tool-name tokens matched whole."""

NAME_BIGRAMS = frozenset({("run", "code")})
"""Adjacent token pairs matched in order — ``run_code`` in Amendment 2 §5's list."""

ALL_KINDS: frozenset[Kind] = frozenset(
    {"code_exec", "read_sensitive", "write", "destructive", "egress"}
)
"""Rule H: code subsumes every other kind by construction."""


def _name_evidence(tool_name: str) -> str | None:
    tokens = name_tokens(tool_name)
    for token in tokens:
        if token in NAME_TOKENS:
            return f"tool name {tool_name!r} carries token {token!r}"
        for stem in NAME_TOKEN_STEMS:
            if token.startswith(stem):
                return f"tool name {tool_name!r} carries token {token!r}"
    for first, second in pairwise(tokens):
        if (first, second) in NAME_BIGRAMS:
            return f"tool name {tool_name!r} carries tokens {first!r} {second!r}"
    return None


def extract(tool_name: str, input_schema: JsonSchema, description: str | None) -> list[Candidate]:
    """Extract the Rule H candidate for one tool, or nothing.

    Returns at most one candidate carrying every piece of evidence found, so a
    reviewer sees the whole case rather than the first hit.
    """
    evidence: list[str] = []

    if (name_hit := _name_evidence(tool_name)) is not None:
        evidence.append(name_hit)

    result = walk_schema(input_schema)
    if result.status is TraversalStatus.COMPLETE:
        tool_text = (description or "").lower()
        for prop in result.properties:
            if not is_unconstrained_string(prop.subschema):
                continue
            if prop.name in CODE_PARAMETER_FIELDS:
                evidence.append(f"{prop.pointer}: caller-supplied code parameter {prop.name!r}")
            elif prop.name == QUERY_PARAMETER_FIELD:
                param_text = str(prop.subschema.get("description", "")).lower()
                markers = [m for m in RAW_QUERY_MARKERS if m in param_text or m in tool_text]
                if markers:
                    evidence.append(
                        f"{prop.pointer}: 'query' described as raw query text ({markers[0]!r})"
                    )
                # else: ambiguous — deliberately fails OPEN. See the module docstring
                # before "fixing" this: an R5 on every search tool is the failure
                # mode Amendment 2 §5 chose the false negative over.

    if not evidence:
        return []
    return [
        Candidate(
            signal="code_execution",
            tier="R5",
            evidence="; ".join(evidence),
            rule="Rule H",
            kinds=ALL_KINDS,
        )
    ]

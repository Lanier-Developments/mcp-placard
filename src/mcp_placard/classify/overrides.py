"""The override allowlist — the only mechanism that may ever lower a tier.

AGENTS.md: *never silently downgrade a tier because a server declares itself safe.*
A downgrade happens only through an explicit, attributable entry in the consuming
repo's own configuration — never automatically, never because of a declared
annotation, never inferred. This module applies that allowlist and nothing else;
it never raises a tier and never guesses at intent from anything the server sent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import get_args

from ..errors import UsageError
from ..manifest.models import TIER_ORDER, OverrideApplied, Tier


@dataclass(frozen=True)
class OverrideEntry:
    """One allowlist entry, supplied entirely by the consuming repo's own config —
    Placard never infers or suggests one.
    """

    entry_id: str
    """An identifier for this entry, recorded on the manifest so a reader can trace
    which config line produced a downgrade — not a free-text explanation."""

    tool: str
    """Exact tool name this entry applies to. No pattern or wildcard matching —
    the same "explicit and closed" discipline Rule C's field list applies."""

    tier: Tier
    """The tier to downgrade to. An entry whose tier is not strictly lower than the
    tool's inferred tier is inert — see :func:`apply`."""

    reason: str = ""


def apply(
    tool_name: str, inferred_tier: Tier, overrides: list[OverrideEntry]
) -> tuple[Tier, OverrideApplied | None]:
    """Apply the first matching override entry, if any, and only if it downgrades.

    Returns the (possibly unchanged) tier and, when an entry actually applied, an
    :class:`~mcp_placard.manifest.models.OverrideApplied` record naming the entry
    and the tier the tool would have carried without it.
    """
    for entry in overrides:
        if entry.tool != tool_name:
            continue
        if TIER_ORDER.index(entry.tier) >= TIER_ORDER.index(inferred_tier):
            continue  # not a downgrade — inert, never raises or no-ops silently as a "match"
        return entry.tier, OverrideApplied(
            entry=entry.entry_id, without_override_tier=inferred_tier
        )
    return inferred_tier, None


_VALID_TIERS = frozenset(get_args(Tier))


def load_overrides(path: Path) -> list[OverrideEntry]:
    """Load the override allowlist from a JSON file: a list of objects, each with
    ``entry_id``, ``tool``, ``tier``, and optionally ``reason``.

    A malformed file is a usage error (exit 10), never a traceback and never a
    silently-ignored file — an override config that fails to load must not be
    mistaken for "no overrides configured."
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UsageError(f"cannot read override config {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise UsageError(f"{path}: not valid JSON: {exc}") from exc

    if not isinstance(document, list):
        raise UsageError(f"{path}: expected a JSON array of override entries")

    entries: list[OverrideEntry] = []
    for index, raw_entry in enumerate(document):
        if not isinstance(raw_entry, dict):
            raise UsageError(f"{path}[{index}]: expected an object")
        try:
            entry_id, tool, tier = raw_entry["entry_id"], raw_entry["tool"], raw_entry["tier"]
        except KeyError as exc:
            raise UsageError(f"{path}[{index}]: missing required field {exc}") from exc
        if tier not in _VALID_TIERS:
            raise UsageError(f"{path}[{index}]: {tier!r} is not one of {sorted(_VALID_TIERS)}")
        entries.append(
            OverrideEntry(
                entry_id=entry_id, tool=tool, tier=tier, reason=raw_entry.get("reason", "")
            )
        )
    return entries

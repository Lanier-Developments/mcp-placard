"""Amendment 4 (ruleset 3.7): Rule D condition 2, replacement-pair form.

The construction under test: a locator and a replacement addressed at a path.
`str_replace(path, old_str, new_str)` came from `mcp-local-filesystem` — a server we
wrote — so per the 2026-10-16 dispatch it enters this corpus as *lifted*, not
held-out, and must not be scored as generalisation.
"""

from __future__ import annotations

from typing import Any

import pytest

from mcp_placard.classify.schema_walk import walk_schema
from mcp_placard.classify.signals.schema_shape import (
    extract,
    find_substitution_evidence,
)


def _string_props(**names: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": dict(names)}


def _tiers(schema: dict[str, Any]) -> list[tuple[str, str | None, frozenset]]:
    candidates, _status = extract(schema)
    return [(c.tier, c.rule, c.kinds) for c in candidates]


STR = {"type": "string"}

STR_REPLACE = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Absolute path to the file to edit"},
        "old_str": STR,
        "new_str": STR,
        "description": STR,
    },
    "required": ["path", "old_str", "new_str"],
}


def _r5_write_pair(schema: dict[str, Any]) -> list:
    candidates, _status = extract(schema)
    return [c for c in candidates if c.tier == "R5" and c.rule == "Rule D" and "write" in c.kinds]


# ------------------------------------------------------------------- must fire


def test_str_replace_is_r5_write() -> None:
    """The lifted case itself, exactly as `mcp-local-filesystem` declares it."""
    hits = _r5_write_pair(STR_REPLACE)
    assert len(hits) == 1
    assert "replacement pair 'old_str'/'new_str'" in hits[0].evidence


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("old", "new"),
        ("old_string", "new_string"),
        ("oldText", "newText"),
        ("str_old", "str_new"),  # suffix position pairs the same as prefix
    ],
)
def test_pair_spellings_all_reduce_to_the_construction(old: str, new: str) -> None:
    schema = _string_props(path=STR, **{old: STR, new: STR})
    assert _r5_write_pair(schema), (old, new)


def test_wrapper_lift_fires_whatever_the_wrapper_is_named() -> None:
    """`edits: [{oldText, newText}]` reaches condition 2 today only through the
    name `edits`; the lift must carry a renamed wrapper too."""
    for wrapper in ("edits", "changes", "patches"):
        schema = {
            "type": "object",
            "properties": {
                "path": STR,
                wrapper: {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"oldText": STR, "newText": STR},
                        "required": ["oldText", "newText"],
                    },
                },
            },
            "required": ["path", wrapper],
        }
        hits = _r5_write_pair(schema)
        assert hits, wrapper
        evidence = hits[0].evidence
        assert f"'{wrapper}'" in evidence or "replacement pair" in evidence


def test_pair_beats_position_exemption() -> None:
    """A path with a position sibling *and* a replacement pair is a write, the
    same precedence a content-carrying sibling has (Amendment 3 §3.4)."""
    schema = _string_props(path=STR, line={"type": "integer"}, old_str=STR, new_str=STR)
    assert _r5_write_pair(schema)


# --------------------------------------------------------------- must not fire


def test_reference_pair_is_a_comparison_not_a_substitution() -> None:
    for stem in ("version", "ref", "commit", "revision"):
        schema = _string_props(path=STR, **{f"old_{stem}": STR, f"new_{stem}": STR})
        assert not _r5_write_pair(schema), stem


def test_single_token_non_pairs_do_not_pair() -> None:
    """`query`/`limit` differ at exactly one position; the differing tokens are
    not a marker pair, so nothing fires."""
    schema = _string_props(path=STR, query=STR, limit=STR)
    assert not _r5_write_pair(schema)


def test_concurrency_token_releases_the_pair() -> None:
    """The guarded-write exemption is shared with the rest of condition 2."""
    schema = _string_props(path=STR, old_str=STR, new_str=STR, if_match=STR)
    assert not _r5_write_pair(schema)


def test_pair_without_a_path_confers_nothing() -> None:
    """Deliberate narrowness: no standalone kind-`write` for a bare pair.
    `update_record(id, old_value, new_value)` is left exactly as before."""
    schema = _string_props(id=STR, old_value=STR, new_value=STR)
    candidates, _status = extract(schema)
    assert all("write" not in c.kinds for c in candidates)
    assert all(c.tier != "R5" for c in candidates)


def test_pair_split_across_anyof_branches_is_not_a_pair() -> None:
    schema = {
        "type": "object",
        "anyOf": [
            {"properties": {"path": STR, "old_str": STR}},
            {"properties": {"new_str": STR}},
        ],
    }
    assert not _r5_write_pair(schema)


def test_patterned_path_does_not_fire() -> None:
    """The unconstrained-pattern requirement is shared with the rest of
    condition 2."""
    schema = _string_props(
        path={"type": "string", "pattern": r"^/workspace/[a-z0-9/_.-]+$"},
        old_str=STR,
        new_str=STR,
    )
    assert not _r5_write_pair(schema)


# ------------------------------------------------------------------- internals


def test_substitution_evidence_sibling_discipline() -> None:
    result = walk_schema(STR_REPLACE)
    evidence = find_substitution_evidence(result.properties)
    assert evidence.pairs == {"": ("old_str", "new_str")}
    assert evidence.wrappers == {}

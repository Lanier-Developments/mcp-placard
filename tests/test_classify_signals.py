"""Direct unit coverage for the smaller signal-extractor mechanics not already
exercised end to end by the fixture matrix — the disagreement table's other two
rows, the combiner's defensive guard, and the remaining verb/description branches.
"""

from __future__ import annotations

import pytest

from mcp_placard.classify.candidates import Candidate
from mcp_placard.classify.combine import combine
from mcp_placard.classify.signals import description, verb
from mcp_placard.classify.signals.annotations import find_disagreements
from mcp_placard.manifest.models import ToolAnnotations

# --------------------------------------------------------------------- combine


def test_combine_raises_on_an_empty_candidate_list() -> None:
    """Defensive: every real caller always has at least one candidate (schema
    shape's Rule B fallback never returns empty), so an empty list here means a
    caller skipped a signal rather than that nothing fired."""
    with pytest.raises(ValueError, match="requires at least one candidate"):
        combine([])


def test_combine_keeps_every_candidate_as_a_citation_not_only_the_winner() -> None:
    candidates = [
        Candidate(signal="schema_shape", tier="R1", evidence="a", rule="Rule B"),
        Candidate(signal="tool_name_verb", tier="R3", evidence="b", rule=None),
    ]
    tier, citations, kinds = combine(candidates)
    assert tier == "R3"
    assert {c.tier for c in citations} == {"R1", "R3"}
    assert kinds == []


# ---------------------------------------------------------------- annotations


def test_destructive_hint_false_at_r5_is_a_disagreement() -> None:
    annotations = ToolAnnotations(destructive_hint=False)
    disagreements = find_disagreements(annotations, "R5")
    assert len(disagreements) == 1
    assert disagreements[0].annotation == "destructiveHint"


def test_destructive_hint_false_below_r5_is_not_a_disagreement() -> None:
    annotations = ToolAnnotations(destructive_hint=False)
    assert find_disagreements(annotations, "R4") == []


def test_open_world_hint_false_at_r4_is_a_disagreement() -> None:
    annotations = ToolAnnotations(open_world_hint=False)
    disagreements = find_disagreements(annotations, "R4")
    assert len(disagreements) == 1
    assert disagreements[0].annotation == "openWorldHint"


def test_open_world_hint_false_at_r5_is_not_this_disagreement() -> None:
    """Scoped to R4 specifically — Rule A's "a closed world does not take a url"
    reasoning is about egress, not about R5's irreversible actions."""
    annotations = ToolAnnotations(open_world_hint=False)
    assert find_disagreements(annotations, "R5") == []


def test_destructive_hint_true_over_declaring_is_never_a_finding() -> None:
    """The table's fifth-row contrast: over-declaring risk costs nothing."""
    annotations = ToolAnnotations(destructive_hint=True)
    assert find_disagreements(annotations, "R1") == []


def test_no_annotations_at_all_produces_no_disagreements() -> None:
    assert find_disagreements(None, "R5") == []


def test_a_declared_safety_claim_never_becomes_a_candidate() -> None:
    """Amendment 2 §7 is one-directional: ``readOnlyHint: true`` is a claim the
    declarer benefits from and never enters Rule F's maximum. Only a claim
    *against* interest (``destructiveHint: true``) does — see
    ``tests/test_classify_kinds.py``."""
    from mcp_placard.classify.signals import annotations as annotations_module

    assert annotations_module.extract(ToolAnnotations(read_only_hint=True)) == []
    assert annotations_module.extract(ToolAnnotations(destructive_hint=False)) == []
    assert annotations_module.extract(None) == []


# ----------------------------------------------------------------------- verb


def test_a_destructive_verb_alone_is_r3_corroborating() -> None:
    candidates = verb.extract("remove_temp_file")
    assert len(candidates) == 1
    assert candidates[0].tier == "R3"


def test_an_unrecognized_verb_produces_no_candidate() -> None:
    assert verb.extract("search_documents") == []


# ------------------------------------------------------------------ description


def test_a_bare_tenant_word_without_this_your_does_not_match() -> None:
    """`describe_server`'s own R0 worked example says "configured workspace
    root" — the false positive this module is written to avoid."""
    assert description.extract("Return the configured workspace root.") == []


def test_an_explicit_tenant_phrase_matches() -> None:
    candidates = description.extract("Return the collections available in this workspace.")
    assert len(candidates) == 1
    assert candidates[0].tier == "R1"


def test_no_description_produces_no_candidate() -> None:
    assert description.extract(None) == []
    assert description.extract("") == []

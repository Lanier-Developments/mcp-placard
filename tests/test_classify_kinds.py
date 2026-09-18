"""Amendment 2 mechanics, as synthetic unit fixtures: the kind axis, Rule D's three
conditions, Rule C's ``to`` exemption, Rule H, annotation escalation, and
whole-token verb matching. The same rules against real server schemas live in
``test_classify_real_servers.py``.
"""

from __future__ import annotations

import json

import pytest

from mcp_placard.classify import classify_tool
from mcp_placard.classify.candidates import Candidate
from mcp_placard.classify.combine import combine
from mcp_placard.classify.signals import description, verb
from mcp_placard.manifest.models import (
    KIND_ORDER,
    Citation,
    ToolAnnotations,
    ToolClassification,
    ToolEntry,
)

from .test_classify_fixture_matrix import FIXTURE_MATRIX


def _tool(
    name: str,
    schema: dict,
    description_text: str | None = None,
    **annotation_kwargs: bool,
) -> ToolEntry:
    annotations = ToolAnnotations(**annotation_kwargs) if annotation_kwargs else None
    return ToolEntry(
        name=name,
        input_schema=schema,
        description=description_text,
        schema_hash="0" * 64,
        description_hash="0" * 64,
        annotations=annotations,
    )


def _props(**fields: dict) -> dict:
    return {"type": "object", "properties": fields}


STR: dict = {"type": "string"}

# ------------------------------------------------------------- Rule D, §1


def test_a_bare_path_on_a_read_is_not_a_destination() -> None:
    """The defect Amendment 2 §1 corrects: ``path`` on ``get_file`` is a source."""
    result = classify_tool(_tool("get_file", _props(path=STR), "Return a file."), [])
    assert result.tier == "R1"
    assert all(c.tier != "R5" for c in result.citations)


def test_condition_1_an_independent_write_signal_makes_the_path_a_destination() -> None:
    result = classify_tool(_tool("create_directory", _props(path=STR)), [])
    assert result.tier == "R5"
    assert any("independent signal already established" in c.evidence for c in result.citations)
    assert "write" in result.kinds


def test_condition_2_a_content_sibling_makes_the_path_a_destination() -> None:
    """No verb at all — the sibling alone establishes the write."""
    result = classify_tool(_tool("blorp", _props(path=STR, content=STR)), [])
    assert result.tier == "R5"
    assert any("content-carrying sibling 'content'" in c.evidence for c in result.citations)


def test_condition_3_a_destination_named_field_is_a_destination_by_itself() -> None:
    result = classify_tool(_tool("relocate", _props(source=STR, destination=STR)), [])
    assert result.tier == "R5"
    assert any("destination-named parameter 'destination'" in c.evidence for c in result.citations)


def test_a_content_sibling_in_a_different_object_does_not_count() -> None:
    schema = _props(path=STR, payload={"type": "object", "properties": {"content": STR}})
    result = classify_tool(_tool("blorp", schema), [])
    assert result.tier == "R1"


def test_a_concurrency_token_still_exempts_every_condition() -> None:
    result = classify_tool(_tool("write_record", _props(path=STR, content=STR, if_match=STR)), [])
    assert result.tier == "R3"
    assert result.reversibility == "verified"


# ------------------------------------------------------------- Rule C, §2


def test_to_with_a_from_sibling_and_no_content_is_an_edge_not_a_recipient() -> None:
    result = classify_tool(_tool("link", _props(**{"from": STR, "to": STR})), [])
    assert result.tier != "R4"
    assert "egress" not in result.kinds


def test_to_with_a_from_sibling_and_a_body_is_still_a_message() -> None:
    result = classify_tool(_tool("send", _props(**{"from": STR, "to": STR, "body": STR})), [])
    assert result.tier == "R4"
    assert "egress" in result.kinds


def test_the_exemption_needs_from_in_the_same_object() -> None:
    schema = _props(**{"to": STR, "meta": {"type": "object", "properties": {"from": STR}}})
    result = classify_tool(_tool("send", schema), [])
    assert result.tier == "R4"


def test_the_exemption_applies_to_to_only() -> None:
    result = classify_tool(_tool("page", _props(**{"from": STR, "recipient": STR})), [])
    assert result.tier == "R4"


# ------------------------------------------------------------- Rule H, §5

ALL_KINDS = {"code_exec", "read_sensitive", "write", "destructive", "egress"}


def test_a_code_parameter_is_r5_with_every_kind() -> None:
    result = classify_tool(_tool("run_command", _props(command=STR)), [])
    assert result.tier == "R5"
    assert set(result.kinds) == ALL_KINDS
    assert any(c.rule == "Rule H" for c in result.citations)


def test_a_command_enum_is_a_selector_not_a_program() -> None:
    schema = _props(command={"type": "string", "enum": ["start", "stop"]})
    result = classify_tool(_tool("service", schema), [])
    assert "code_exec" not in result.kinds


def test_an_ambiguous_query_fails_open() -> None:
    """The one deliberate fail-open in the taxonomy."""
    result = classify_tool(
        _tool("search_repositories", _props(query=STR), "Search repositories."), []
    )
    assert "code_exec" not in result.kinds
    assert result.tier == "R1"


def test_a_query_described_as_sql_is_code() -> None:
    schema = _props(query={"type": "string", "description": "Raw SQL to run against the database"})
    result = classify_tool(_tool("query_db", schema), [])
    assert "code_exec" in result.kinds
    assert result.tier == "R5"


def test_a_query_language_named_in_the_tool_description_is_code() -> None:
    result = classify_tool(_tool("graph", _props(query=STR), "Execute a Cypher query."), [])
    assert "code_exec" in result.kinds


@pytest.mark.parametrize(
    "name",
    [
        "evaluate_js",
        "browser_evaluate",
        "exec",
        "execute_script",
        "open_shell",
        "run_code",
        "do_unsafe_thing",
    ],
)
def test_name_tokens_mark_code_execution(name: str) -> None:
    result = classify_tool(_tool(name, _props(x=STR)), [])
    assert "code_exec" in result.kinds, name


@pytest.mark.parametrize(
    "name", ["search_code", "coder_profile", "runner_status", "shellfish_menu"]
)
def test_near_miss_names_do_not(name: str) -> None:
    result = classify_tool(_tool(name, _props(x=STR)), [])
    assert "code_exec" not in result.kinds, name


def test_readonly_on_a_code_execution_tool_is_the_severest_disagreement() -> None:
    result = classify_tool(_tool("eval", _props(code=STR), read_only_hint=True), [])
    [finding] = [d for d in result.disagreements if d.annotation == "readOnlyHint"]
    assert "caller-supplied code" in finding.reading


# ----------------------------------------------------- annotations, §7


def test_destructive_hint_true_floors_at_r3_with_kind_destructive() -> None:
    result = classify_tool(_tool("frobnicate", _props(x=STR), destructive_hint=True), [])
    assert result.tier == "R3"
    assert result.kinds == ["destructive"]
    assert result.disagreements == []
    assert any(c.signal == "declared_annotations" for c in result.citations)


def test_destructive_hint_true_does_not_lower_a_higher_tier() -> None:
    result = classify_tool(_tool("notify", _props(to=STR), destructive_hint=True), [])
    assert result.tier == "R4"


def test_declared_danger_makes_a_bare_path_a_destination() -> None:
    """§7 feeds §1's condition 1: the annotation is an independent R3 signal."""
    result = classify_tool(_tool("blorp", _props(path=STR), destructive_hint=True), [])
    assert result.tier == "R5"


# ------------------------------------------------------- verb tokens, §8


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("git_add", "write"),
        ("createOrUpdateFile", "write"),
        ("merge_pull_request", "write"),
        ("fork_repository", "write"),
        ("git_reset", "destructive"),
        ("repo.push", "write"),
        ("browser-move-mouse", "write"),
    ],
)
def test_verbs_match_as_whole_tokens_anywhere_in_the_name(name: str, kind: str) -> None:
    [candidate] = verb.extract(name)
    assert candidate.tier == "R3"
    assert candidate.kinds == {kind}


@pytest.mark.parametrize(
    "name", ["settings_get", "toggle-subscriber-updates", "additive_blend", "resetter_info"]
)
def test_a_verb_inside_a_longer_token_does_not_match(name: str) -> None:
    assert verb.extract(name) == []


def test_rotate_over_a_credential_noun_carries_kind_destructive() -> None:
    [candidate] = verb.extract("rotate_api_credential")
    assert candidate.tier == "R5"
    assert candidate.kinds == {"destructive"}


# ------------------------------------------------------ description, §3, §8


def test_directory_is_no_longer_a_sensitive_domain() -> None:
    assert description.extract("List the directory contents.") == []


def test_a_sensitive_read_carries_kind_read_sensitive() -> None:
    [candidate] = description.extract("Read messages from the mail inbox.")
    assert candidate.kinds == {"read_sensitive"}


def test_a_sensitive_action_keeps_the_tier_floor_but_not_the_read_kind() -> None:
    """``send_email`` touches mail, so R2 still floors it; it does not *read* mail."""
    [candidate] = description.extract("Send an email to the given recipients.")
    assert candidate.tier == "R2"
    assert candidate.kinds == frozenset()


# ------------------------------------------------------------ kinds, §3


def test_kinds_are_the_union_in_canonical_order() -> None:
    _tier, _citations, kinds = combine(
        [
            Candidate(signal="schema_shape", tier="R4", evidence="a", kinds=frozenset({"egress"})),
            Candidate(signal="tool_name_verb", tier="R3", evidence="b", kinds=frozenset({"write"})),
            Candidate(
                signal="schema_shape", tier="R2", evidence="c", kinds=frozenset({"read_sensitive"})
            ),
        ]
    )
    assert kinds == ["read_sensitive", "egress", "write"]
    assert kinds == sorted(kinds, key=KIND_ORDER.index)


def test_every_kind_on_a_tool_traces_to_a_citation_across_the_matrix() -> None:
    """Same shape as the tier-citation test: a kind with no evidence is a bug."""
    for label, tool, _expected in FIXTURE_MATRIX:
        result = classify_tool(tool, [])
        cited = {kind for citation in result.citations for kind in citation.kinds}
        assert set(result.kinds) == cited, label


def test_overrides_lower_the_tier_but_never_touch_kinds() -> None:
    from mcp_placard.classify.overrides import OverrideEntry

    tool = _tool("notify", _props(to=STR))
    override = OverrideEntry(entry_id="ov-1", tool="notify", tier="R1", reason="internal relay")
    result = classify_tool(tool, [override])
    assert result.tier == "R1"
    assert result.kinds == ["egress"]


def test_empty_kinds_serialize_as_absent_and_nonempty_as_present() -> None:
    bare = ToolClassification(tool="t", tier="R1")
    assert "kinds" not in bare.model_dump(mode="json")
    assert "kinds" not in json.loads(bare.model_dump_json())

    typed = ToolClassification(tool="t", tier="R4", kinds=["egress"])
    assert typed.model_dump(mode="json")["kinds"] == ["egress"]

    citation = Citation(signal="schema_shape", tier="R1", evidence="x")
    assert "kinds" not in citation.model_dump(mode="json")

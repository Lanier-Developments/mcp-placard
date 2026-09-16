"""The Phase 2 fixture matrix from `docs/TAXONOMY.md` (Amendment 1, section 3).

Two worked examples and one near-miss per tier, R0 through R5 — the acceptance
criterion is that this whole matrix is green. AGENTS.md requires fixture coverage
in *both* directions for every tier: a tool that belongs in it, and a near-miss
that does not. Every row here is exactly one of those two directions.

Schemas and descriptions are written from the worked examples in `docs/TAXONOMY.md`
where the document gives one verbatim; the amendment's replacement fixtures
(`create_issue`, `update_record`, `get_link_preview`, `rotate_display_name`, etc.)
don't come with an exact schema in the text, so these are authored to match the
taxonomy's own prose about what makes each one the tier it is.
"""

from __future__ import annotations

import pytest

from mcp_placard.classify import classify_tool
from mcp_placard.manifest.models import Tier, ToolAnnotations, ToolEntry


def _tool(
    name: str,
    schema: dict,
    description: str | None = None,
    **annotation_kwargs: bool,
) -> ToolEntry:
    annotations = ToolAnnotations(**annotation_kwargs) if annotation_kwargs else None
    return ToolEntry(
        name=name,
        input_schema=schema,
        description=description,
        schema_hash="0" * 64,
        description_hash="0" * 64,
        annotations=annotations,
    )


# ------------------------------------------------------------------------- R0

R0_EXAMPLE_1 = _tool(
    "describe_server",
    {"type": "object", "properties": {}, "additionalProperties": False},
    "Return this server's name, version, and configured workspace root.",
    read_only_hint=True,
    open_world_hint=False,
)

R0_EXAMPLE_2 = _tool(
    "list_supported_formats",
    {
        "type": "object",
        "properties": {"category": {"type": "string", "enum": ["image", "audio", "text"]}},
        "additionalProperties": False,
    },
    "Return the list of supported format categories.",
)

R0_NEAR_MISS = _tool(  # Rule B: a bare free-text field is R1, not R0
    "search_public_docs",
    {"type": "object", "properties": {"query": {"type": "string"}}},
    "Search public documentation.",
)

# ------------------------------------------------------------------------- R1

R1_EXAMPLE_1 = _tool(
    "search_documents",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            "include_archived": {"type": "boolean"},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    "Search indexed workspace documents and return matching excerpts.",
)

R1_EXAMPLE_2 = _tool(
    "get_build_status",
    {
        "type": "object",
        "properties": {
            "pipeline_id": {"type": "string", "pattern": "^[a-z0-9-]{1,64}$"},
            "include_logs": {"type": "boolean"},
        },
        "required": ["pipeline_id"],
        "additionalProperties": False,
    },
    "Return the current status of a pipeline run.",
)

R1_NEAR_MISS = _tool(  # get_build_status(include_secrets) -> R2
    "get_build_status",
    {
        "type": "object",
        "properties": {
            "pipeline_id": {"type": "string", "pattern": "^[a-z0-9-]{1,64}$"},
            "include_secrets": {"type": "boolean"},
        },
        "required": ["pipeline_id"],
        "additionalProperties": False,
    },
    "Return the current status of a pipeline run.",
)

# ------------------------------------------------------------------------- R2

R2_EXAMPLE_1 = _tool(
    "read_inbox",
    {
        "type": "object",
        "properties": {
            "folder": {"type": "string"},
            "since": {"type": "string", "format": "date-time"},
            "max_messages": {"type": "integer", "maximum": 500},
        },
        "additionalProperties": False,
    },
    "Read email messages from the workspace inbox, optionally filtered by folder and time range.",
    read_only_hint=True,
)

R2_EXAMPLE_2 = _tool(
    "list_directory_users",
    {
        "type": "object",
        "properties": {
            "group": {"type": "string"},
            "include_contact_details": {"type": "boolean", "default": False},
            "page_size": {"type": "integer", "maximum": 1000},
        },
        "additionalProperties": False,
    },
    "List users in the organizational directory, optionally scoped to one group.",
)

R2_NEAR_MISS = _tool(  # Rule A: get_link_preview(url) -> R4
    "get_link_preview",
    {
        "type": "object",
        "properties": {"url": {"type": "string", "format": "uri"}},
        "required": ["url"],
        "additionalProperties": False,
    },
    "Fetch a preview (title, description) for the given URL.",
    read_only_hint=True,
)

# ------------------------------------------------------------------------- R3

R3_EXAMPLE_1 = _tool(
    "create_issue",
    {
        "type": "object",
        "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
        "required": ["title"],
        "additionalProperties": False,
    },
    "Create a new issue in the tracker.",
)

R3_EXAMPLE_2 = _tool(  # Rule D: if_match -> reversibility "verified"
    "update_record",
    {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "body": {"type": "string"},
            "if_match": {"type": "string"},
        },
        "required": ["id", "body"],
        "additionalProperties": False,
    },
    "Update an existing record, guarded by optimistic concurrency.",
)

R3_NEAR_MISS = _tool(  # Rule C: create_issue(webhook_url) -> R4
    "create_issue",
    {
        "type": "object",
        "properties": {"title": {"type": "string"}, "webhook_url": {"type": "string"}},
        "required": ["title"],
        "additionalProperties": False,
    },
    "Create a new issue and notify a webhook on completion.",
)

# ------------------------------------------------------------------------- R4

R4_EXAMPLE_1 = _tool(
    "send_email",
    {
        "type": "object",
        "properties": {
            "to": {"type": "array", "items": {"type": "string", "format": "email"}, "minItems": 1},
            "subject": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["to", "subject", "body"],
        "additionalProperties": False,
    },
    "Send an email on the user's behalf to one or more recipients.",
    open_world_hint=True,
)

R4_EXAMPLE_2 = _tool(
    "fetch_url",
    {
        "type": "object",
        "properties": {
            "url": {"type": "string", "format": "uri"},
            "timeout_seconds": {"type": "number", "maximum": 60},
        },
        "required": ["url"],
        "additionalProperties": False,
    },
    "Fetch an arbitrary HTTP(S) URL and return the response body as text.",
    read_only_hint=True,
    open_world_hint=True,
)

R4_NEAR_MISS = _tool(  # Rule E: a recognized host-pinning form -> R1
    "fetch_doc",
    {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "format": "uri",
                "pattern": r"^https://docs\.internal\.example\.com/",
            }
        },
        "required": ["url"],
        "additionalProperties": False,
    },
    "Fetch a document from the internal documentation site.",
)

# ------------------------------------------------------------------------- R5

R5_EXAMPLE_1 = _tool(
    "delete_workspace",
    {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string"},
            "force": {"type": "boolean", "default": False},
            "confirm_phrase": {"type": "string", "const": "DELETE"},
        },
        "required": ["workspace_id", "confirm_phrase"],
        "additionalProperties": False,
    },
    "Permanently delete a workspace and every document in it. This cannot be undone.",
    destructive_hint=True,
)

R5_EXAMPLE_2 = _tool(  # Rule D: unconstrained destination path, no concurrency token
    "write_note",
    {
        "type": "object",
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"],
        "additionalProperties": False,
    },
    "Write a note to an arbitrary path — unguarded.",
)

R5_NEAR_MISS = _tool(  # verb alone must not decide it — ordinary domain noun
    "rotate_display_name",
    {
        "type": "object",
        "properties": {"user_id": {"type": "string"}, "new_display_name": {"type": "string"}},
        "required": ["user_id", "new_display_name"],
        "additionalProperties": False,
    },
    "Change a user's display name.",
)

FIXTURE_MATRIX: list[tuple[str, ToolEntry, Tier]] = [
    ("R0 example 1: describe_server", R0_EXAMPLE_1, "R0"),
    ("R0 example 2: list_supported_formats", R0_EXAMPLE_2, "R0"),
    ("R0 near-miss: search_public_docs(query)", R0_NEAR_MISS, "R1"),
    ("R1 example 1: search_documents", R1_EXAMPLE_1, "R1"),
    ("R1 example 2: get_build_status", R1_EXAMPLE_2, "R1"),
    ("R1 near-miss: get_build_status(include_secrets)", R1_NEAR_MISS, "R2"),
    ("R2 example 1: read_inbox", R2_EXAMPLE_1, "R2"),
    ("R2 example 2: list_directory_users", R2_EXAMPLE_2, "R2"),
    ("R2 near-miss: get_link_preview(url)", R2_NEAR_MISS, "R4"),
    ("R3 example 1: create_issue", R3_EXAMPLE_1, "R3"),
    ("R3 example 2: update_record(if_match)", R3_EXAMPLE_2, "R3"),
    ("R3 near-miss: create_issue(webhook_url)", R3_NEAR_MISS, "R4"),
    ("R4 example 1: send_email", R4_EXAMPLE_1, "R4"),
    ("R4 example 2: fetch_url", R4_EXAMPLE_2, "R4"),
    ("R4 near-miss: fetch_doc (host-pinned)", R4_NEAR_MISS, "R1"),
    ("R5 example 1: delete_workspace", R5_EXAMPLE_1, "R5"),
    ("R5 example 2: write_note (unguarded)", R5_EXAMPLE_2, "R5"),
    ("R5 near-miss: rotate_display_name", R5_NEAR_MISS, "R3"),
]


@pytest.mark.parametrize(
    ("label", "tool", "expected_tier"),
    FIXTURE_MATRIX,
    ids=[row[0] for row in FIXTURE_MATRIX],
)
def test_fixture_matrix(label: str, tool: ToolEntry, expected_tier: Tier) -> None:
    result = classify_tool(tool, [])
    assert result.tier == expected_tier, label


def test_every_classification_in_the_matrix_cites_at_least_one_signal() -> None:
    """A tier with no stated reasoning is an opinion, not a finding — asserted
    globally across the whole matrix, per the Phase 2 acceptance criteria."""
    for label, tool, _expected in FIXTURE_MATRIX:
        result = classify_tool(tool, [])
        assert result.citations, f"{label}: no citation for tier {result.tier}"


def test_get_link_preview_carries_the_readonly_disagreement() -> None:
    """Acceptance criterion, verbatim: ``get_link_preview(url)`` classifies R4 with
    ``readOnlyHint: true`` present and unheeded."""
    result = classify_tool(R2_NEAR_MISS, [])
    assert result.tier == "R4"
    assert any(d.annotation == "readOnlyHint" for d in result.disagreements)


def test_a_readonly_tool_with_a_to_field_classifies_r4_with_a_disagreement() -> None:
    """Acceptance criterion, verbatim: a tool with ``readOnlyHint: true`` and a
    ``to`` field classifies R4 with a disagreement finding."""
    tool = _tool(
        "notify",
        {"type": "object", "properties": {"to": {"type": "string"}}, "required": ["to"]},
        "Send a notification.",
        read_only_hint=True,
    )
    result = classify_tool(tool, [])
    assert result.tier == "R4"
    assert any(d.annotation == "readOnlyHint" for d in result.disagreements)


def test_write_note_unguarded_is_r5_and_with_if_match_moves_to_r3_verified() -> None:
    """Acceptance criterion, verbatim: unguarded ``write_note(path, content)``
    classifies R5; adding ``if_match`` moves it to R3 ``verified``."""
    unguarded = classify_tool(R5_EXAMPLE_2, [])
    assert unguarded.tier == "R5"

    guarded = _tool(
        "write_note",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "if_match": {"type": "string"},
            },
            "required": ["path", "content"],
        },
        "Write a note, guarded by optimistic concurrency.",
    )
    result = classify_tool(guarded, [])
    assert result.tier == "R3"
    assert result.reversibility == "verified"

"""Phase 2.1 acceptance criteria against real server surfaces.

The Phase 2.1 brief: *"all of these are drawn from real surfaces in your report, so
capture them as fixtures from the actual server schemas rather than hand-written
approximations."* ``tests/fixtures/real_servers/`` holds each server's ``tools/list``
as captured on 2026-09-17 — name, description, ``inputSchema``, ``annotations`` —
and nothing else. These are regression fixtures for the classifier, not for the
transport layer, so they carry no hashes and no server metadata beyond the name.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_placard.classify import classify_manifest
from mcp_placard.manifest import build_manifest
from mcp_placard.manifest.models import Manifest, ToolClassification

from .conftest import make_raw

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "real_servers"
SERVERS = sorted(path.stem for path in FIXTURES.glob("*.json"))


def _classified(server: str) -> Manifest:
    document = json.loads((FIXTURES / f"{server}.json").read_text(encoding="utf-8"))
    return classify_manifest(build_manifest(make_raw(document["tools"], server_name=server)))


@pytest.fixture(scope="module")
def surfaces() -> dict[str, Manifest]:
    return {server: _classified(server) for server in SERVERS}


def _tool(surfaces: dict[str, Manifest], server: str, name: str) -> ToolClassification:
    return surfaces[server].classification_by_tool()[name]


def _chain(surfaces: dict[str, Manifest], server: str) -> list[str]:
    return [f.summary for f in surfaces[server].findings if f.kind == "chain_exfil"]


# ------------------------------------------------------------------ filesystem

FILESYSTEM_READS = [
    "read_file",
    "read_text_file",
    "read_media_file",
    "list_directory",
    "list_directory_with_sizes",
    "directory_tree",
    "get_file_info",
    "search_files",
]


@pytest.mark.parametrize("name", FILESYSTEM_READS)
def test_filesystem_reads_are_reads(surfaces: dict[str, Manifest], name: str) -> None:
    entry = _tool(surfaces, "filesystem", name)
    assert entry.tier in {"R1", "R2"}, (name, entry.tier)
    assert not any(d.annotation == "readOnlyHint" for d in entry.disagreements), name


def test_filesystem_move_file_is_r5_on_destination(surfaces: dict[str, Manifest]) -> None:
    entry = _tool(surfaces, "filesystem", "move_file")
    assert entry.tier == "R5"
    assert any("'destination'" in c.evidence and c.rule == "Rule D" for c in entry.citations)
    assert entry.tier >= "R3"  # destructiveHint: true on its own would already floor it


def test_filesystem_writes_stay_r5(surfaces: dict[str, Manifest]) -> None:
    """The corrections must not let a real write escape: an unguarded path on a
    tool the verb (or a content sibling) establishes as writing is still R5."""
    for name in ("write_file", "edit_file", "create_directory"):
        assert _tool(surfaces, "filesystem", name).tier == "R5", name


def test_filesystem_raises_no_chain(surfaces: dict[str, Manifest]) -> None:
    assert _chain(surfaces, "filesystem") == []


# ---------------------------------------------------------------------- memory


@pytest.mark.parametrize("name", ["create_relations", "delete_relations"])
def test_memory_graph_edges_are_not_egress(surfaces: dict[str, Manifest], name: str) -> None:
    entry = _tool(surfaces, "memory", name)
    assert entry.tier != "R4"
    assert "egress" not in entry.kinds
    assert not any(d.annotation == "openWorldHint" for d in entry.disagreements)


def test_memory_delete_entities_no_longer_reaches_asserted(surfaces: dict[str, Manifest]) -> None:
    entry = _tool(surfaces, "memory", "delete_entities")
    assert entry.tier == "R3"
    assert entry.reversibility == "unverifiable"


def test_memory_raises_no_chain(surfaces: dict[str, Manifest]) -> None:
    assert _chain(surfaces, "memory") == []


# ---------------------------------------------------------------------- github


def test_github_create_or_update_file_is_verified_on_sha(surfaces: dict[str, Manifest]) -> None:
    entry = _tool(surfaces, "github", "create_or_update_file")
    assert entry.tier == "R3"
    assert entry.reversibility == "verified"


@pytest.mark.parametrize(
    "name",
    ["merge_pull_request", "fork_repository", "add_issue_comment", "create_branch", "update_issue"],
)
def test_github_mutations_are_at_least_r3(surfaces: dict[str, Manifest], name: str) -> None:
    entry = _tool(surfaces, "github", name)
    assert entry.tier >= "R3", (name, entry.tier)
    assert "write" in entry.kinds


def test_github_get_file_contents_is_a_read(surfaces: dict[str, Manifest]) -> None:
    assert _tool(surfaces, "github", "get_file_contents").tier == "R1"


def test_github_review_comment_path_is_a_reference_not_a_destination(
    surfaces: dict[str, Manifest],
) -> None:
    """Amendment 3 §3.1 and §3.4: ``comments[].{path, position, body}`` — ``body`` is
    a comment body, not file content, so condition 2 does not fire; and ``position``
    beside ``path`` makes it a reference, so condition 1 does not either."""
    entry = _tool(surfaces, "github", "create_pull_request_review")
    assert entry.tier == "R3"
    assert entry.kinds == ["write"]
    assert entry.reversibility == "unverifiable"


def test_github_push_files_is_still_a_file_write(surfaces: dict[str, Manifest]) -> None:
    """Same shape as the review, but ``files[].{path, content}`` — ``content`` is
    on the list and the tool must stay R5."""
    entry = _tool(surfaces, "github", "push_files")
    assert entry.tier == "R5"
    assert any("content-carrying sibling 'content'" in c.evidence for c in entry.citations)


def test_github_search_tools_are_not_code_execution(surfaces: dict[str, Manifest]) -> None:
    """The fail-open on an ambiguous ``query`` parameter, on real descriptions."""
    for name in ("search_code", "search_issues", "search_repositories", "search_users"):
        entry = _tool(surfaces, "github", name)
        assert entry.tier == "R1", name
        assert "code_exec" not in entry.kinds, name


# ------------------------------------------------------------------------- git


@pytest.mark.parametrize(
    "name", ["git_add", "git_commit", "git_checkout", "git_create_branch", "git_reset"]
)
def test_git_mutation_verbs_are_at_least_r3(surfaces: dict[str, Manifest], name: str) -> None:
    assert _tool(surfaces, "git", name).tier >= "R3", name


def test_git_reset_escalates_on_its_own_destructive_hint(surfaces: dict[str, Manifest]) -> None:
    entry = _tool(surfaces, "git", "git_reset")
    assert entry.tier == "R3"
    assert "destructive" in entry.kinds
    assert any(c.signal == "declared_annotations" for c in entry.citations)


def test_git_reads_are_r1_now_that_directory_is_not_sensitive(
    surfaces: dict[str, Manifest],
) -> None:
    for name in ("git_status", "git_log", "git_diff", "git_diff_unstaged", "git_show"):
        assert _tool(surfaces, "git", name).tier == "R1", name


# -------------------------------------------------------------------- playwright

ALL_KINDS = {"code_exec", "read_sensitive", "write", "destructive", "egress"}


@pytest.mark.parametrize("name", ["browser_run_code_unsafe", "browser_evaluate"])
def test_playwright_code_execution_is_r5_with_every_kind(
    surfaces: dict[str, Manifest], name: str
) -> None:
    entry = _tool(surfaces, "playwright", name)
    assert entry.tier == "R5", name
    assert set(entry.kinds) == ALL_KINDS, name
    assert any(c.rule == "Rule H" for c in entry.citations), name


def test_playwright_raises_chain_on_code_execution_alone(surfaces: dict[str, Manifest]) -> None:
    [summary] = _chain(surfaces, "playwright")
    finding = surfaces["playwright"].findings[0]
    assert {"browser_run_code_unsafe", "browser_evaluate"} <= set(finding.tools)
    assert "carries both halves alone" in summary
    assert "tools only" in finding.scope.lower()


def test_playwright_navigate_back_is_not_asserted_on_browser_history(
    surfaces: dict[str, Manifest],
) -> None:
    assert _tool(surfaces, "playwright", "browser_navigate_back").reversibility == "unverifiable"


def test_asserted_is_empty_across_the_batch_and_that_is_the_honest_number(
    surfaces: dict[str, Manifest],
) -> None:
    """Amendment 3 §3.3's standing decision: this assertion is *expected to break*
    once a document-management server (Drive, Notion, Confluence) joins the batch.
    When it does, delete this test — do not weaken the phrase list to keep it."""
    asserted = [
        (server, e.tool)
        for server, m in surfaces.items()
        for e in m.classification
        if e.reversibility == "asserted"
    ]
    assert asserted == []


def test_playwright_navigation_is_still_egress(surfaces: dict[str, Manifest]) -> None:
    for name in ("browser_navigate", "browser_tabs"):
        entry = _tool(surfaces, "playwright", name)
        assert entry.tier == "R4", name
        assert "egress" in entry.kinds


# ----------------------------------------------------------------------- global


def test_every_tool_on_every_server_cites_evidence(surfaces: dict[str, Manifest]) -> None:
    for server, manifest in surfaces.items():
        for entry in manifest.classification:
            assert entry.citations, (server, entry.tool)


def test_every_kind_on_every_server_traces_to_a_citation(surfaces: dict[str, Manifest]) -> None:
    """The Phase 2.1 acceptance criterion, verbatim: every kind assignment carries a
    citation, asserted globally across all fixtures."""
    for server, manifest in surfaces.items():
        for entry in manifest.classification:
            cited = {kind for citation in entry.citations for kind in citation.kinds}
            assert set(entry.kinds) == cited, (server, entry.tool)


def test_no_real_read_sits_at_r5(surfaces: dict[str, Manifest]) -> None:
    """The first flag-back condition in the brief, as a guard: a tool the server
    marks read-only and whose name starts with a read verb must not be R5. If
    this ever fails, stop and report with the schema rather than tuning."""
    read_verbs = ("get", "list", "read", "search", "show", "find", "fetch_info")
    for server, manifest in surfaces.items():
        tools = manifest.tools_by_name()
        for entry in manifest.classification:
            declared_read_only = (
                tools[entry.tool].annotations is not None
                and tools[entry.tool].annotations.read_only_hint is True  # type: ignore[union-attr]
            )
            if declared_read_only and entry.tool.startswith(read_verbs):
                assert entry.tier != "R5", (server, entry.tool)

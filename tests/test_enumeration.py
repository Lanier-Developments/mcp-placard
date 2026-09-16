"""Enumeration mechanics: pagination, capability gating, and failure mapping.

Driven by a fake client rather than a real server so the awkward cases — a server
that paginates forever, a server that advertises nothing, a listing that errors
after a successful handshake — can be produced on demand. The happy path against a
real server lives in ``test_integration.py``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import anyio
import pytest

from mcp_placard.errors import ConnectionFailure, EnumerationError
from mcp_placard.transport.base import MAX_PAGES, collect_surface, connect_and_collect


class WireItem:
    """Stands in for an SDK model: attribute access plus a wire-JSON dump."""

    def __init__(self, **fields: Any) -> None:
        self._fields = fields
        for key, value in fields.items():
            setattr(self, key, value)

    def model_dump(self, **_kwargs: Any) -> dict[str, Any]:
        return {key: value for key, value in self._fields.items() if value is not None}


def _capabilities(*, tools: bool = True, resources: bool = True, prompts: bool = True) -> WireItem:
    """Capabilities as the SDK presents them: an object per declared capability."""
    return WireItem(
        tools={"listChanged": False} if tools else None,
        resources={"subscribe": False} if resources else None,
        prompts={"listChanged": False} if prompts else None,
    )


def _page(attribute: str, items: list[WireItem], next_cursor: str | None = None) -> Any:
    return SimpleNamespace(**{attribute: items, "next_cursor": next_cursor})


class FakeClient:
    """A client that answers listings from a scripted set of pages."""

    def __init__(
        self,
        *,
        tool_pages: list[Any] | None = None,
        capabilities: Any = None,
        failing: str | None = None,
    ) -> None:
        self.server_info = WireItem(name="fake", version="1.0")
        self.instructions = "instructions"
        self.server_capabilities = capabilities if capabilities is not None else _capabilities()
        self._tool_pages = tool_pages or [_page("tools", [WireItem(name="only")])]
        self._failing = failing
        self._tool_calls = 0

    async def list_tools(self, *, cursor: str | None = None) -> Any:
        if self._failing == "tools":
            raise RuntimeError("server refused tools/list")
        page = self._tool_pages[self._tool_calls]
        self._tool_calls += 1
        return page

    async def list_resources(self, *, cursor: str | None = None) -> Any:
        return _page("resources", [WireItem(name="r", uri="file:///r")])

    async def list_resource_templates(self, *, cursor: str | None = None) -> Any:
        return _page("resource_templates", [WireItem(name="t", uriTemplate="file:///{p}")])

    async def list_prompts(self, *, cursor: str | None = None) -> Any:
        return _page("prompts", [WireItem(name="p")])


def _collect(client: FakeClient) -> Any:
    return anyio.run(lambda: collect_surface(client))


def test_a_single_page_listing_is_collected() -> None:
    surface = _collect(FakeClient())
    assert [tool["name"] for tool in surface.tools] == ["only"]
    assert surface.server_info == {"name": "fake", "version": "1.0"}
    assert surface.instructions == "instructions"


def test_pagination_is_followed_to_exhaustion() -> None:
    pages = [
        _page("tools", [WireItem(name="a")], next_cursor="p2"),
        _page("tools", [WireItem(name="b")], next_cursor="p3"),
        _page("tools", [WireItem(name="c")]),
    ]
    surface = _collect(FakeClient(tool_pages=pages))
    assert [tool["name"] for tool in surface.tools] == ["a", "b", "c"]


def test_an_endless_cursor_raises_rather_than_returning_a_partial_surface() -> None:
    """A truncated surface hashed as though it were complete would make the next
    scan report the missing tools as "added" — a scanner that manufactures false
    history is worse than one that errors."""
    endless = [
        _page("tools", [WireItem(name=f"t{index}")], next_cursor="more")
        for index in range(MAX_PAGES + 1)
    ]
    with pytest.raises(EnumerationError, match="did not terminate"):
        _collect(FakeClient(tool_pages=endless))


def test_undeclared_capabilities_are_not_requested() -> None:
    """Asking a server for something it never advertised produces a protocol error,
    not an empty list."""
    client = FakeClient(capabilities=_capabilities(resources=False, prompts=False))
    surface = _collect(client)
    assert surface.tools
    assert surface.resources == []
    assert surface.resource_templates == []
    assert surface.prompts == []


def test_a_server_advertising_nothing_yields_an_empty_surface() -> None:
    client = FakeClient(capabilities=_capabilities(tools=False, resources=False, prompts=False))
    surface = _collect(client)
    assert surface.tools == surface.resources == surface.prompts == []


def test_declared_capabilities_are_all_enumerated() -> None:
    surface = _collect(FakeClient())
    assert surface.resources and surface.resource_templates and surface.prompts


def test_a_listing_failure_after_the_handshake_is_an_enumeration_error() -> None:
    with pytest.raises(EnumerationError, match="failed to enumerate"):
        _collect(FakeClient(failing="tools"))


def test_connect_and_collect_maps_a_construction_failure_to_connection_failure() -> None:
    def explode() -> Any:
        raise OSError("no such process")

    with pytest.raises(ConnectionFailure, match="cannot connect to fake target"):
        anyio.run(lambda: connect_and_collect(explode, description="fake target", timeout=5))


def test_connect_and_collect_preserves_enumeration_errors() -> None:
    """A typed error from inside must not be re-labelled as a connection failure:
    "we could not reach it" and "it answered badly" are different diagnoses."""

    class Ctx:
        async def __aenter__(self) -> FakeClient:
            return FakeClient(failing="tools")

        async def __aexit__(self, *_exc: object) -> None:
            return None

    with pytest.raises(EnumerationError):
        anyio.run(lambda: connect_and_collect(Ctx, description="fake target", timeout=5))

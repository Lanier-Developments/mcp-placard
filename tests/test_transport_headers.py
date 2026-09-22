"""HTTP request headers from ``header_env``: attached for the scan, stored nowhere."""

from __future__ import annotations

from mcp_placard.transport.http import HeaderedStreamableHTTP, build_http_client


def test_headers_are_attached_to_the_http_client() -> None:
    client = build_http_client({"Authorization": "Bearer sentinel-token"})
    assert client.headers["authorization"] == "Bearer sentinel-token"


def test_no_headers_means_the_sdk_default_client() -> None:
    client = build_http_client(None)
    assert "authorization" not in client.headers


def test_the_transport_keeps_headers_private() -> None:
    transport = HeaderedStreamableHTTP("https://example.test/mcp", {"X-Key": "sentinel"})
    assert "sentinel" not in repr(transport)
    assert "sentinel" not in str(transport)

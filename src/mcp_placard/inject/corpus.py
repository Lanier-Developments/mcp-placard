"""Turn an encoded corpus sample into a manifest to analyse.

Malicious samples are stored base64-encoded (Phase 3 §5 handling rule) and decoded
only here, at the moment they become data under test. This module exists in
``src/`` rather than ``tests/`` so the held-out scorer (``scripts/score_heldout.py``)
and the test suite build samples identically — a held-out score produced by a
different construction path would measure the wrong thing.

Nothing here is used by ``scan`` or ``diff``.
"""

from __future__ import annotations

import base64
from typing import Any

from ..manifest import build_manifest
from ..manifest.models import Manifest
from ..manifest.raw import RawSurface

BASELINE_TOOL: dict[str, Any] = {
    "name": "noop",
    "description": "Does nothing.",
    "inputSchema": {"type": "object", "properties": {}},
}


def decode_payload(sample: dict[str, Any]) -> str:
    return base64.b64decode(sample["payload_b64"]).decode("utf-8")


def sample_manifest(sample: dict[str, Any]) -> tuple[Manifest, str]:
    """Build the manifest a sample describes and return it with the element id the
    payload was placed in, so a test can assert the finding landed *there*.

    ``element`` is one of ``tool_description``, ``property_description``,
    ``instructions``. ``server_name`` (optional) sets the declared ``initialize``
    name, for samples that exercise the own-name exemption. ``tool`` names the owning
    tool and its parameter names (all unconstrained strings); ``property`` names
    which parameter's description carries the payload.
    """
    payload = decode_payload(sample)
    element_kind = sample["element"]
    instructions: str | None = None
    tools: list[dict[str, Any]] = []
    element_id: str

    if element_kind == "instructions":
        instructions = payload
        tools = [BASELINE_TOOL]
        element_id = "server:instructions"
    else:
        tool = sample["tool"]
        props: dict[str, Any] = {name: {"type": "string"} for name in tool.get("params", [])}
        description = "A tool."
        if element_kind == "tool_description":
            description = payload
            element_id = f"tool:{tool['name']}/description"
        elif element_kind == "property_description":
            prop = sample["property"]
            props.setdefault(prop, {"type": "string"})["description"] = payload
            element_id = f"tool:{tool['name']}/inputSchema/properties/{prop}/description"
        else:
            raise ValueError(f"unknown element kind {element_kind!r}")
        tools = [
            {
                "name": tool["name"],
                "description": description,
                "inputSchema": {"type": "object", "properties": props},
            }
        ]

    raw = RawSurface(
        server_info={"name": sample.get("server_name") or "corpus-sample", "version": "0"},
        capabilities={"tools": {"listChanged": False}},
        environment={},
        instructions=instructions,
        tools=tools,
        resources=[],
        resource_templates=[],
        prompts=[],
    )
    return build_manifest(raw), element_id

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
from .surface import escape_pointer

BASELINE_TOOL: dict[str, Any] = {
    "name": "noop",
    "description": "Does nothing.",
    "inputSchema": {"type": "object", "properties": {}},
}

# The prompt and resource a non-tool sample hangs from. Fixed, because the element
# id has to be reconstructable from the sample alone, and a sample that named its
# own prompt or URI would be one more thing for an author to get subtly wrong.
PROMPT_NAME = "corpus_prompt"
RESOURCE_URI = "file:///corpus/sample.txt"
RESOURCE_TEMPLATE_URI = "file:///corpus/{path}"

FILLER = "A prompt."


def _sibling_tools(sample: dict[str, Any]) -> list[dict[str, Any]]:
    """The other tools the fictional server exposes, from the optional ``siblings`` list.

    A sample could not previously say that its server has any tool but the one it names,
    so a description referring to a tool *on the same server* — "call ``build_status``
    first" — was a foreign reference by construction and ``cross_scope`` fired correctly
    on a server that did not exist. Held-out v2's benign file was the first thing to ask
    for this: malicious samples never needed siblings, because ``cross_scope`` wants
    references that really are foreign.

    Absent, behaves exactly as before.
    """
    return [
        {
            "name": name,
            "description": "A tool.",
            "inputSchema": {"type": "object", "properties": {}},
        }
        for name in sample.get("siblings") or []
    ]


def decode_payload(sample: dict[str, Any]) -> str:
    return base64.b64decode(sample["payload_b64"]).decode("utf-8")


def sample_manifest(sample: dict[str, Any]) -> tuple[Manifest, str]:
    """Build the manifest a sample describes and return it with the element id the
    payload was placed in, so a test can assert the finding landed *there*.

    ``element`` is one of ``tool_description``, ``property_description``,
    ``instructions``, ``prompt_description``, ``prompt_argument_description``,
    ``resource_description``, ``resource_template_description``. ``server_name``
    (optional) sets the declared ``initialize`` name, for samples that exercise the
    own-name exemption.

    For the tool-owned kinds, ``tool`` names the owning tool and its parameter names
    (all unconstrained strings) and ``property`` names which parameter's description
    carries the payload. The prompt and resource kinds have no owning tool — they
    hang from :data:`PROMPT_NAME` / :data:`RESOURCE_URI` / :data:`RESOURCE_TEMPLATE_URI`
    and ``tool`` is ignored — and for ``prompt_argument_description`` ``property``
    names the argument.

    Two optional fields let a sample state a server the defaults cannot express, both
    added after held-out v2's benign file needed them. ``uri`` overrides the synthesized
    resource or template URI, which matters because under ruleset 3.3 the URI *is* the
    evidence: a fixed URI removes the author's ability to state the case being made.
    ``siblings`` lists further tool names on the fictional server, so a same-server
    reference can be written without ``cross_scope`` firing on a server of one tool.

    The element ids returned here must match ``surface.enumerate_text`` exactly: the
    scorer selects findings by equality on this string, so a divergence would score a
    correct detection as a miss.
    """
    payload = decode_payload(sample)
    element_kind = sample["element"]
    instructions: str | None = None
    tools: list[dict[str, Any]] = [BASELINE_TOOL, *_sibling_tools(sample)]
    prompts: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []
    resource_templates: list[dict[str, Any]] = []
    element_id: str

    if element_kind == "instructions":
        instructions = payload
        element_id = "server:instructions"
    elif element_kind == "prompt_description":
        prompts = [{"name": PROMPT_NAME, "description": payload}]
        element_id = f"prompt:{PROMPT_NAME}/description"
    elif element_kind == "prompt_argument_description":
        argument = sample["property"]
        prompts = [
            {
                "name": PROMPT_NAME,
                "description": FILLER,
                "arguments": [{"name": argument, "description": payload, "required": False}],
            }
        ]
        element_id = f"prompt:{PROMPT_NAME}/arguments/{argument}/description"
    elif element_kind == "resource_description":
        uri = sample.get("uri") or RESOURCE_URI
        resources = [{"name": "corpus_resource", "uri": uri, "description": payload}]
        element_id = f"resource:{escape_pointer(uri)}/description"
    elif element_kind == "resource_template_description":
        uri = sample.get("uri") or RESOURCE_TEMPLATE_URI
        resource_templates = [
            {
                "name": "corpus_template",
                "uriTemplate": uri,
                "description": payload,
            }
        ]
        element_id = f"resource_template:{escape_pointer(uri)}/description"
    elif element_kind in ("tool_description", "property_description"):
        tool = sample["tool"]
        props: dict[str, Any] = {name: {"type": "string"} for name in tool.get("params", [])}
        description = "A tool."
        if element_kind == "tool_description":
            description = payload
            element_id = f"tool:{tool['name']}/description"
        else:
            prop = sample["property"]
            props.setdefault(prop, {"type": "string"})["description"] = payload
            element_id = f"tool:{tool['name']}/inputSchema/properties/{prop}/description"
        tools = [
            {
                "name": tool["name"],
                "description": description,
                "inputSchema": {"type": "object", "properties": props},
            },
            *_sibling_tools(sample),
        ]
    else:
        raise ValueError(f"unknown element kind {element_kind!r}")

    capabilities: dict[str, Any] = {"tools": {"listChanged": False}}
    if prompts:
        capabilities["prompts"] = {"listChanged": False}
    if resources or resource_templates:
        capabilities["resources"] = {"listChanged": False, "subscribe": False}

    raw = RawSurface(
        server_info={"name": sample.get("server_name") or "corpus-sample", "version": "0"},
        capabilities=capabilities,
        environment={},
        instructions=instructions,
        tools=tools,
        resources=resources,
        resource_templates=resource_templates,
        prompts=prompts,
    )
    return build_manifest(raw), element_id

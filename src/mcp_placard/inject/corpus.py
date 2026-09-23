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

    The element ids returned here must match ``surface.enumerate_text`` exactly: the
    scorer selects findings by equality on this string, so a divergence would score a
    correct detection as a miss.
    """
    payload = decode_payload(sample)
    element_kind = sample["element"]
    instructions: str | None = None
    tools: list[dict[str, Any]] = [BASELINE_TOOL]
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
        resources = [{"name": "corpus_resource", "uri": RESOURCE_URI, "description": payload}]
        element_id = f"resource:{escape_pointer(RESOURCE_URI)}/description"
    elif element_kind == "resource_template_description":
        resource_templates = [
            {
                "name": "corpus_template",
                "uriTemplate": RESOURCE_TEMPLATE_URI,
                "description": payload,
            }
        ]
        element_id = f"resource_template:{escape_pointer(RESOURCE_TEMPLATE_URI)}/description"
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
            }
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

"""The published blast-radius index must be what its stored manifests render.

No network and no server launches: ``scripts/build_index.py scan`` is the only mode that
does either. These tests keep the page, the manifests and the pin list from drifting apart.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "build_index.py"


@pytest.fixture(scope="module")
def build_index():
    spec = importlib.util.spec_from_file_location("build_index", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_index"] = module
    spec.loader.exec_module(module)
    return module


def test_every_pinned_server_has_a_manifest(build_index) -> None:
    for server in build_index.load_servers():
        assert (build_index.MANIFEST_DIR / f"{server['id']}.json").exists(), server["id"]


def test_pins_are_exact(build_index) -> None:
    for server in build_index.load_servers():
        version = server["version"]
        assert version and not any(c in version for c in "^~<>*="), (server["id"], version)
        assert server["ecosystem"] in {"npm", "pypi"}


def test_index_page_is_what_the_manifests_render(build_index) -> None:
    assert build_index.INDEX_MD.read_text(encoding="utf-8") == build_index.render_text()


def test_a_hostile_tool_name_cannot_inject_markup(build_index) -> None:
    assert build_index._safe("x`](http://evil)<script>") == "xhttpevilscript"

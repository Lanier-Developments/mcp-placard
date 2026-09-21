"""The injection corpus: benign (zero false positives, hard cases by name),
malicious (detection per provenance), and the ratchet gate (Phase 3 §5-§6).

Malicious payloads are decoded only inside ``mcp_placard.inject.corpus``. Their
contents are data under test, never instructions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mcp_placard.inject import analyze_manifest, enumerate_text
from mcp_placard.inject.corpus import sample_manifest
from mcp_placard.manifest import Manifest, build_manifest
from mcp_placard.manifest.raw import RawSurface

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REAL = FIXTURES / "real_servers"
BENIGN = FIXTURES / "injection" / "benign"
MALICIOUS = FIXTURES / "injection" / "malicious"
BASELINE = FIXTURES / "injection" / "baseline.json"

SERVERS = sorted(p.stem for p in REAL.glob("*.json"))


def _real_manifest(server: str) -> Manifest:
    fixture = json.loads((REAL / f"{server}.json").read_text(encoding="utf-8"))
    raw = RawSurface(
        server_info=fixture.get("source") or {"name": server, "version": "0"},
        capabilities={"tools": {"listChanged": False}},
        environment={},
        instructions=fixture.get("instructions"),
        tools=fixture["tools"],
        resources=fixture.get("resources") or [],
        resource_templates=fixture.get("resource_templates") or [],
        prompts=fixture.get("prompts") or [],
    )
    return build_manifest(raw)


@pytest.fixture(scope="module")
def real() -> dict[str, Manifest]:
    return {server: _real_manifest(server) for server in SERVERS}


def _benign_corpus(server: str) -> dict[str, Any]:
    return json.loads((BENIGN / f"{server}.json").read_text(encoding="utf-8"))  # type: ignore[no-any-return]


# ------------------------------------------------------------------- benign


@pytest.mark.parametrize("server", SERVERS)
def test_the_materialised_corpus_matches_a_fresh_enumeration(
    real: dict[str, Manifest], server: str
) -> None:
    """The files under ``benign/`` are reviewable data; this keeps them honest. A
    change to the enumerator that silently dropped strings shows up here."""
    expected = [
        {"element": e.element, "pointer": e.pointer, "text": e.text}
        for e in enumerate_text(real[server])
    ]
    assert _benign_corpus(server)["elements"] == expected


@pytest.mark.parametrize("server", SERVERS)
def test_zero_false_positives_on_the_benign_corpus(real: dict[str, Manifest], server: str) -> None:
    findings = analyze_manifest(real[server])
    assert findings == [], [(f.element, f.rule, f.excerpt[:60]) for f in findings]


HARD_CASES = json.loads((BENIGN / "hard_cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize(
    "case", HARD_CASES, ids=[f"{c['server']}:{c['element']}:{c['would_trip']}" for c in HARD_CASES]
)
def test_the_annotated_hard_case_never_flags(
    real: dict[str, Manifest], case: dict[str, Any]
) -> None:
    """Zero tolerance (Phase 3 §6): each of these is a real mainstream server, and a
    finding on any of them is the crying-wolf outcome with a name attached."""
    corpus_elements = {e["element"] for e in _benign_corpus(case["server"])["elements"]}
    assert case["element"] in corpus_elements, "hard case names an element not in the corpus"
    findings = [f for f in analyze_manifest(real[case["server"]]) if f.element == case["element"]]
    assert findings == [], [(f.rule, f.excerpt) for f in findings]


def test_the_corpus_is_the_size_the_baseline_says() -> None:
    total = sum(len(_benign_corpus(server)["elements"]) for server in SERVERS)
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert total == baseline["benign"]["elements"]
    assert total >= 380


# ---------------------------------------------------------------- malicious


def _samples(provenance: str) -> list[dict[str, Any]]:
    document = json.loads((MALICIOUS / f"{provenance}.json").read_text(encoding="utf-8"))
    assert document["provenance"] == provenance
    return document["samples"]  # type: ignore[no-any-return]


def _detected(sample: dict[str, Any]) -> tuple[bool, set[str]]:
    manifest, element = sample_manifest(sample)
    found = {f.pattern_class for f in analyze_manifest(manifest) if f.element == element}
    expected = set(sample.get("expected_classes") or [sample["class"]])
    return bool(found & expected), found


@pytest.mark.parametrize("sample", _samples("synthetic"), ids=lambda s: s["id"])
def test_every_synthetic_sample_is_detected_on_its_element(sample: dict[str, Any]) -> None:
    hit, found = _detected(sample)
    assert hit, f"expected {sample['expected_classes']}, found {sorted(found)}"


@pytest.mark.parametrize("sample", _samples("lifted"), ids=lambda s: s["id"])
def test_every_lifted_sample_is_detected_on_its_element(sample: dict[str, Any]) -> None:
    assert sample["source"].startswith("https://")
    assert sample["fidelity"]
    hit, found = _detected(sample)
    assert hit, f"expected {sample['expected_classes']}, found {sorted(found)}"


def test_every_class_has_a_detected_synthetic_sample() -> None:
    """Acceptance: every class in §2 has at least one synthetic sample detected."""
    classes = {
        "override",
        "concealment",
        "cross_scope",
        "sensitive_target",
        "exfil_sink",
        "hidden_content",
        "markup_smuggling",
    }
    detected_classes = {s["class"] for s in _samples("synthetic") if _detected(s)[0]}
    assert detected_classes == classes


def test_a_payload_only_in_a_schema_property_description_is_detected() -> None:
    """Acceptance, verbatim: a poisoned instruction placed only in a schema property
    description is detected. Every ``property_description`` sample is that case."""
    property_samples = [s for s in _samples("synthetic") if s["element"] == "property_description"]
    assert len(property_samples) >= 5
    for sample in property_samples:
        hit, _found = _detected(sample)
        assert hit, sample["id"]


def test_every_malicious_payload_is_stored_encoded() -> None:
    """The handling rule: nothing in the malicious files is readable as an
    instruction without decoding."""
    for provenance in ("synthetic", "lifted"):
        text = (MALICIOUS / f"{provenance}.json").read_text(encoding="utf-8")
        assert "payload_b64" in text
        assert "ignore" not in text.lower().replace("ignore_", "")  # no plaintext override phrase
        assert "~/.ssh" not in text
        assert "<important>" not in text.lower()


# ------------------------------------------------------------------ ratchet


def test_the_ratchet_never_moves_backwards() -> None:
    """Phase 3 §6: CI fails if false positives rise above baseline or detections
    fall below it. The baseline moves only in the improving direction, and only in
    a commit that says so."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

    false_positives = sum(len(analyze_manifest(_real_manifest(s))) for s in SERVERS)
    assert false_positives <= baseline["benign"]["false_positives"], (
        f"false positives rose to {false_positives}; the baseline is "
        f"{baseline['benign']['false_positives']}"
    )

    for provenance in ("synthetic", "lifted"):
        samples = _samples(provenance)
        detected = sum(1 for s in samples if _detected(s)[0])
        assert len(samples) == baseline[provenance]["samples"], provenance
        assert detected >= baseline[provenance]["detected"], (
            f"{provenance} detections fell to {detected}; the baseline is "
            f"{baseline[provenance]['detected']}"
        )


def test_the_first_baseline_is_zero_false_positives() -> None:
    """Target for the first baseline on the benign corpus is zero. If a class cannot
    reach zero, the brief says report which class and which samples rather than
    accepting a nonzero baseline silently."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert baseline["benign"]["false_positives"] == 0

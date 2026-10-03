from __future__ import annotations

from pathlib import Path

import pytest

from control_layer.domain.models.signature import Signature
from control_layer.infrastructure.signatures.yaml_signature_feed import YamlSignatureFeed

REAL_SIGNATURES_FILE = (
    Path(__file__).resolve().parents[4] / "config" / "attack_signatures.yaml"
)

SAMPLE_YAML = """
version: 1
updated_at: "2026-10-03"
signatures:
  - id: SIG-001
    title: Ignore previous instructions
    pattern: 'ignore (all |any )?(the )?(previous|prior) instructions'
    categories: [prompt_injection]
    severity: high
    reference: "OWASP LLM01"
    owasp: [LLM01, ASI01]
    points: [prompt, tool_result]
"""

SAMPLE_YAML_V2 = SAMPLE_YAML + (
    "  - id: SIG-002\n"
    "    title: Second signature\n"
    "    pattern: 'second pattern'\n"
    "    categories: [code_exec]\n"
    "    severity: critical\n"
    "    points: [prompt]\n"
)


@pytest.mark.skipif(
    not REAL_SIGNATURES_FILE.exists(),
    reason="Backend/config/attack_signatures.yaml not present",
)
async def test_loads_real_sample_signatures_file() -> None:
    feed = YamlSignatureFeed(REAL_SIGNATURES_FILE)

    signatures = await feed.signatures()

    assert len(signatures) > 0
    assert all(isinstance(sig, Signature) for sig in signatures)


async def test_loads_signatures_from_tmp_file(tmp_path: Path) -> None:
    path = tmp_path / "attack_signatures.yaml"
    path.write_text(SAMPLE_YAML, encoding="utf-8")
    feed = YamlSignatureFeed(path)

    signatures = await feed.signatures()

    assert len(signatures) == 1
    assert signatures[0].id == "SIG-001"
    assert signatures[0].categories == ["prompt_injection"]


async def test_reload_picks_up_new_signatures(tmp_path: Path) -> None:
    path = tmp_path / "attack_signatures.yaml"
    path.write_text(SAMPLE_YAML, encoding="utf-8")
    feed = YamlSignatureFeed(path)
    await feed.signatures()

    path.write_text(SAMPLE_YAML_V2, encoding="utf-8")
    await feed.reload()

    signatures = await feed.signatures()
    assert [sig.id for sig in signatures] == ["SIG-001", "SIG-002"]


async def test_reload_keeps_last_good_on_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "attack_signatures.yaml"
    path.write_text(SAMPLE_YAML, encoding="utf-8")
    feed = YamlSignatureFeed(path)
    await feed.signatures()

    path.write_text("not: [valid, yaml", encoding="utf-8")
    await feed.reload()

    signatures = await feed.signatures()
    assert [sig.id for sig in signatures] == ["SIG-001"]


async def test_missing_file_falls_back_to_empty_fixture(tmp_path: Path) -> None:
    path = tmp_path / "missing.yaml"
    feed = YamlSignatureFeed(path)

    signatures = await feed.signatures()

    assert signatures == []

from __future__ import annotations

from pathlib import Path

import pytest

from control_layer.infrastructure.mcp.mcp_server_registry import (
    McpServerRegistry,
    build_tool_descriptor,
    load_server_configs,
)

REPO_ROOT = Path(__file__).resolve().parents[5]
BACKEND_DIR = REPO_ROOT / "Backend"
REAL_MCP_SERVERS_FILE = BACKEND_DIR / "config" / "mcp_servers.yaml"
GITHUB_DEMO_SERVER = REPO_ROOT / "demo" / "mcp" / "github.py"

SAMPLE_YAML = """
servers:
  - name: github
    transport: stdio
    command: python
    args: ["-m", "demo.mcp.github"]
    cwd: ".."
    env: { PYTHONUTF8: "1" }
    tools:
      get_readme: { tags: [read_external] }
      delete_branch: { tags: [destructive] }
"""


def test_load_server_configs_parses_servers_list(tmp_path: Path) -> None:
    path = tmp_path / "mcp_servers.yaml"
    path.write_text(SAMPLE_YAML, encoding="utf-8")

    configs = load_server_configs(path)

    assert len(configs) == 1
    assert configs[0]["name"] == "github"
    assert configs[0]["args"] == ["-m", "demo.mcp.github"]


@pytest.mark.skipif(
    not REAL_MCP_SERVERS_FILE.exists(), reason="Backend/config/mcp_servers.yaml not present"
)
def test_load_server_configs_parses_real_sample_file() -> None:
    configs = load_server_configs(REAL_MCP_SERVERS_FILE)

    names = {cfg["name"] for cfg in configs}
    assert "github" in names
    assert "eu-customers" in names


def test_build_tool_descriptor_merges_tags() -> None:
    tools_config = {"delete_branch": {"tags": ["destructive"]}}

    descriptor = build_tool_descriptor(
        "github", "delete_branch", "Delete a branch", {"type": "object"}, tools_config
    )

    assert descriptor.qualified_name == "github.delete_branch"
    assert descriptor.tags == ["destructive"]
    assert descriptor.scope == "write"


def test_build_tool_descriptor_merges_data_region() -> None:
    tools_config = {"read": {"tags": [], "data_region": "eu_customers"}}

    descriptor = build_tool_descriptor("eu-customers", "read", "Read", {}, tools_config)

    assert descriptor.data_region == "eu_customers"
    assert descriptor.scope == "read"


def test_build_tool_descriptor_defaults_when_tool_not_in_config() -> None:
    descriptor = build_tool_descriptor("ci", "get_run", "Get a CI run", {}, {})

    assert descriptor.tags == []
    assert descriptor.data_region is None
    assert descriptor.scope == "read"


@pytest.mark.skipif(
    not GITHUB_DEMO_SERVER.exists(),
    reason="demo/mcp/github.py not present (another stream owns it)",
)
async def test_registry_connects_to_real_github_demo_server(tmp_path: Path) -> None:
    config_path = tmp_path / "mcp_servers.yaml"
    config_path.write_text(SAMPLE_YAML, encoding="utf-8")
    registry = McpServerRegistry(config_path, base_dir=BACKEND_DIR)

    try:
        await registry.start()

        status = registry.status()
        assert status["github"]["status"] == "connected"

        tools = registry.list_tools()
        tool_names = {t.name for t in tools}
        assert {"list_branches", "get_readme", "delete_branch"}.issubset(tool_names)

        get_readme = next(t for t in tools if t.name == "get_readme")
        assert get_readme.tags == ["read_external"]
        delete_branch = next(t for t in tools if t.name == "delete_branch")
        assert delete_branch.tags == ["destructive"]
        assert delete_branch.scope == "write"

        session = registry.session_for("github")
        assert session is not None
        result = await session.call_tool("list_branches", {"repo": "web-app"})
        assert result.isError is False
    finally:
        await registry.aclose()


@pytest.mark.skipif(
    not GITHUB_DEMO_SERVER.exists(),
    reason="demo/mcp/github.py not present (another stream owns it)",
)
async def test_registry_tolerates_a_server_that_fails_to_start(tmp_path: Path) -> None:
    config_path = tmp_path / "mcp_servers.yaml"
    config_path.write_text(
        SAMPLE_YAML
        + "\n"
        + (
            "  - name: broken\n"
            "    transport: stdio\n"
            "    command: python\n"
            "    args: [\"-m\", \"demo.mcp.does_not_exist\"]\n"
            "    cwd: \"..\"\n"
        ),
        encoding="utf-8",
    )
    registry = McpServerRegistry(config_path, base_dir=BACKEND_DIR)

    try:
        await registry.start()

        status = registry.status()
        assert status["github"]["status"] == "connected"
        assert status["broken"]["status"] == "failed"
        assert status["broken"]["error"] is not None

        tool_names = {t.name for t in registry.list_tools()}
        assert "list_branches" in tool_names
    finally:
        await registry.aclose()

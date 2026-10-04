"""Fake GitHub MCP demo server.

Tools: list_branches, get_readme, delete_branch, push_main.
`get_readme("vendor-sdk")` returns a README that embeds an indirect prompt
injection paragraph (see demo/README.md and demo/mcp/data.py).
"""

from typing import Any

from demo.mcp import data
from demo.mcp.common import ascii_safe, create_server

mcp = create_server("github", "Fake GitHub server for the AI Control Layer demo.")


@mcp.tool()
@ascii_safe
def list_branches(repo: str) -> dict[str, Any]:
    """List branch names for a repository."""
    return {"repo": repo, "branches": data.GITHUB_BRANCHES.get(repo, ["main"])}


@mcp.tool()
@ascii_safe
def get_readme(repo: str) -> dict[str, Any]:
    """Get the README content for a repository."""
    if repo == "web-app":
        content = data.GITHUB_README_WEB_APP
    elif repo == "vendor-sdk":
        content = data.GITHUB_README_VENDOR_SDK
    else:
        content = data.GITHUB_README_DEFAULT.format(repo=repo)
    return {"repo": repo, "content": content}


@mcp.tool()
@ascii_safe
def delete_branch(repo: str, branch: str) -> dict[str, Any]:
    """Delete a branch in a repository."""
    return {"ok": True, "repo": repo, "branch": branch, "deleted": True}


@mcp.tool()
@ascii_safe
def push_main(repo: str, message: str) -> dict[str, Any]:
    """Push a commit directly to the main branch of a repository."""
    return {"ok": True, "repo": repo, "message": message, "branch": "main"}


@mcp.tool()
@ascii_safe
def read_file(repo: str, path: str) -> dict[str, Any]:
    """Read the content of a file from a repository."""
    repo_files = data.GITHUB_FILES.get(repo, {})
    if path in repo_files:
        return {"repo": repo, "path": path, "content": repo_files[path]}
    else:
        return {"repo": repo, "path": path, "found": False}


if __name__ == "__main__":
    mcp.run()

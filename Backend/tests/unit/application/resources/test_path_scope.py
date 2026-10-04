from __future__ import annotations

import pytest

from control_layer.application.resources.path_scope import path_allowed
from control_layer.domain.models.resource import PathScope

_REPO_SCOPE = PathScope(
    allow=["src/**", "docs/**", "README.md"],
    deny=["**/.env", "secrets/**", "**/*.pem"],
)


@pytest.mark.parametrize("path", ["src/app.py", "docs/runbook.md", "README.md", "src/a/b/c.py"])
def test_allowed_paths(path: str) -> None:
    decision = path_allowed(path, _REPO_SCOPE)

    assert decision.allowed is True
    assert decision.path == path


def test_deny_wins_over_allow() -> None:
    decision = path_allowed("src/.env", _REPO_SCOPE)

    assert decision.allowed is False
    assert decision.pattern == "**/.env"
    assert decision.reason == "denied by pattern **/.env"


def test_deny_matches_root_level_file_with_recursive_prefix() -> None:
    assert path_allowed(".env", PathScope(deny=["**/.env"])).allowed is False


def test_recursive_wildcard_matches_hidden_segments() -> None:
    decision = path_allowed("src/.hidden/x.py", PathScope(allow=["src/**"]))

    assert decision.allowed is True


def test_allow_list_requires_a_match() -> None:
    decision = path_allowed("other/file.txt", _REPO_SCOPE)

    assert decision.allowed is False
    assert decision.reason == "not in allow list"
    assert decision.pattern is None


def test_empty_allow_list_permits_anything_not_denied() -> None:
    scope = PathScope(deny=["secrets/**"])

    assert path_allowed("anything/else.txt", scope).allowed is True
    assert path_allowed("secrets/key", scope).allowed is False


def test_default_scope_is_unrestricted() -> None:
    assert path_allowed("a/b.txt", PathScope()).allowed is True


@pytest.mark.parametrize(
    "path",
    [
        "/etc/passwd",
        "C:/Windows/win.ini",
        "c:\\Windows\\win.ini",
        "../x",
        "src/../secrets/x",
        "src/..",
    ],
)
def test_absolute_and_traversal_paths_are_rejected(path: str) -> None:
    decision = path_allowed(path, _REPO_SCOPE)

    assert decision.allowed is False
    assert decision.reason == "absolute or traversal path"


def test_traversal_is_rejected_even_when_scope_is_unrestricted() -> None:
    assert path_allowed("a/../b", PathScope()).allowed is False


def test_backslash_separators_are_normalised() -> None:
    assert path_allowed("src\\app.py", _REPO_SCOPE).allowed is True
    assert path_allowed("secrets\\deploy.pem", _REPO_SCOPE).allowed is False
    assert path_allowed("\\etc\\passwd", _REPO_SCOPE).reason == "absolute or traversal path"


def test_matching_is_case_insensitive() -> None:
    assert path_allowed("SRC/App.PY", _REPO_SCOPE).allowed is True
    assert path_allowed("Secrets/Deploy.PEM", _REPO_SCOPE).allowed is False
    assert path_allowed("SRC/.ENV", _REPO_SCOPE).allowed is False


def test_redundant_segments_are_collapsed_before_matching() -> None:
    assert path_allowed("./src//app.py", _REPO_SCOPE).allowed is True
    assert path_allowed("secrets/./deploy.pem", _REPO_SCOPE).allowed is False


def test_extension_deny_matches_nested_files() -> None:
    decision = path_allowed("docs/certs/server.pem", _REPO_SCOPE)

    assert decision.allowed is False
    assert decision.pattern == "**/*.pem"

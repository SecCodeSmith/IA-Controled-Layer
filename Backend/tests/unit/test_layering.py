from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "src" / "control_layer"
BASE = "control_layer"

FORBIDDEN_BY_LAYER: dict[str, tuple[str, ...]] = {
    "domain": (
        f"{BASE}.presentation",
        f"{BASE}.infrastructure",
        f"{BASE}.application",
    ),
    "application": (
        f"{BASE}.presentation",
        f"{BASE}.infrastructure",
    ),
}


def _imported_modules(path: Path) -> list[str]:
    modules: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append(node.module)
            if node.module == BASE:
                modules.extend(f"{BASE}.{alias.name}" for alias in node.names)
    return modules


def _violations(layer: str) -> list[str]:
    forbidden = FORBIDDEN_BY_LAYER[layer]
    found: list[str] = []
    for path in sorted((PACKAGE_ROOT / layer).rglob("*.py")):
        for module in _imported_modules(path):
            if any(module == name or module.startswith(f"{name}.") for name in forbidden):
                found.append(f"{path.relative_to(PACKAGE_ROOT).as_posix()} -> {module}")
    return found


@pytest.mark.parametrize("layer", sorted(FORBIDDEN_BY_LAYER))
def test_inner_layers_do_not_depend_on_outer_layers(layer: str) -> None:
    assert _violations(layer) == []

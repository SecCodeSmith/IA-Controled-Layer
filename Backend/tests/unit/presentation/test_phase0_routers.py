from __future__ import annotations

import pytest

from control_layer.presentation.api.routers import admin_classifier, admin_workbench
from control_layer.presentation.app import _ROUTERS


@pytest.mark.parametrize(
    ("module", "prefix"),
    [(admin_classifier, "/api/classifier"), (admin_workbench, "/api/workbench")],
)
def test_router_is_registered_with_prefix_and_admin_guard(module: object, prefix: str) -> None:
    router = module.router  # type: ignore[attr-defined]

    assert module in _ROUTERS
    assert router.prefix == prefix
    assert router.dependencies
    assert any(route.path == prefix for route in router.routes)

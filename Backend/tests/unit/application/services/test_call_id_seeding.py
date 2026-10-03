from __future__ import annotations

from control_layer.application.services.call_id_seeding import highest_call_id


class _Audit:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    async def export_rows(self) -> list[dict]:
        return self._rows


async def test_returns_highest_numeric_call_id() -> None:
    rows = [{"call_id": "c_000003"}, {"call_id": "c_000139"}, {"call_id": "c_000007"}]
    assert await highest_call_id(_Audit(rows)) == 139


async def test_ignores_malformed_ids_and_handles_empty() -> None:
    assert await highest_call_id(_Audit([])) == 0
    assert await highest_call_id(_Audit([{"call_id": "x_1"}, {}])) == 0

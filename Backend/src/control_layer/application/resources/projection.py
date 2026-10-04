from __future__ import annotations

from typing import Any

from control_layer.domain.models.identity import Identity
from control_layer.domain.models.resource import (
    ColumnScope,
    ProjectionResult,
    ResourceConfig,
    ResourceGrant,
)

_IDENTITY_PREFIX = "$identity."
_OUTSIDE_ROW_SCOPE = {"redacted": "outside row scope"}


def _identity_attribute(identity: Identity, name: str) -> str | None:
    if name == "role":
        return identity.role.value
    if name in ("region", "sub", "location"):
        return getattr(identity, name)
    return None


def _resolve(value: str, identity: Identity) -> str | None:
    if not value.startswith(_IDENTITY_PREFIX):
        return value
    return _identity_attribute(identity, value[len(_IDENTITY_PREFIX) :])


def _resolve_predicate(
    rows: dict[str, str | list[str]], identity: Identity
) -> dict[str, list[str]]:
    resolved: dict[str, list[str]] = {}
    for attribute, expected in rows.items():
        values = [expected] if isinstance(expected, str) else expected
        resolved[attribute] = [
            r for r in (_resolve(v, identity) for v in values) if r is not None
        ]
    return resolved


def _row_matches(record: Any, predicate: dict[str, list[str]]) -> bool:
    if not predicate:
        return True
    if not isinstance(record, dict):
        return False
    return all(
        attribute in record and record[attribute] in accepted
        for attribute, accepted in predicate.items()
    )


def _project_columns(record: Any, columns: ColumnScope) -> tuple[Any, set[str]]:
    if not isinstance(record, dict):
        return record, set()
    kept = {
        name: value
        for name, value in record.items()
        if (columns.allow is None or name in columns.allow) and name not in columns.deny
    }
    return kept, set(record) - set(kept)


def _unchanged(data: Any) -> ProjectionResult:
    return ProjectionResult(data=data)


def _project_records(
    records: list, grant: ResourceGrant, predicate: dict[str, list[str]]
) -> tuple[list, int, set[str]]:
    kept: list = []
    redacted: set[str] = set()
    for record in records:
        if not _row_matches(record, predicate):
            continue
        projected, removed = _project_columns(record, grant.columns)
        kept.append(projected)
        redacted |= removed
    return kept, len(records) - len(kept), redacted


def _result(data: Any, rows_filtered: int, redacted: set[str]) -> ProjectionResult:
    return ProjectionResult(
        data=data,
        rows_filtered=rows_filtered,
        columns_redacted=sorted(redacted),
        changed=bool(rows_filtered or redacted),
    )


def _project_list(
    data: dict, key: str, grant: ResourceGrant, predicate: dict[str, list[str]]
) -> ProjectionResult:
    records = data.get(key)
    if not isinstance(records, list):
        return _unchanged(data)
    kept, filtered, redacted = _project_records(records, grant, predicate)
    return _result({**data, key: kept}, filtered, redacted)


def _project_single(
    data: dict, grant: ResourceGrant, predicate: dict[str, list[str]]
) -> ProjectionResult:
    if not _row_matches(data, predicate):
        return _result(dict(_OUTSIDE_ROW_SCOPE), 1, set())
    projected, redacted = _project_columns(data, grant.columns)
    return _result(projected, 0, redacted)


def project_result(
    data: Any, resource: ResourceConfig, grant: ResourceGrant, identity: Identity
) -> ProjectionResult:
    if not isinstance(data, dict):
        return _unchanged(data)
    predicate = _resolve_predicate(grant.rows, identity)
    if resource.records is not None:
        return _project_list(data, resource.records, grant, predicate)
    return _project_single(data, grant, predicate)

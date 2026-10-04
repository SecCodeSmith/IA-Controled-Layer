from __future__ import annotations

import copy

from control_layer.application.resources.projection import project_result
from control_layer.domain.models.enums import Role
from control_layer.domain.models.resource import ColumnScope, ResourceConfig, ResourceGrant
from tests.unit.application.evaluators.conftest import make_identity

_HR = make_identity(sub="marek", role=Role.hr, region="PL")


def _resource(records: str | None = "rows") -> ResourceConfig:
    return ResourceConfig(id="hr", server="hr-db", records=records)


def _grant(
    rows: dict | None = None, allow: list[str] | None = None, deny: list[str] | None = None
) -> ResourceGrant:
    return ResourceGrant(columns=ColumnScope(allow=allow, deny=deny or []), rows=rows or {})


def _query_data() -> dict:
    return {
        "rows": [
            {"id": "E-2001", "region": "PL", "salary": 14200},
            {"id": "E-2101", "region": "DE", "salary": 11800},
        ],
        "count": 2,
    }


def test_row_predicate_filters_by_identity_region() -> None:
    result = project_result(
        _query_data(), _resource(), _grant(rows={"region": "$identity.region"}), _HR
    )

    assert [row["id"] for row in result.data["rows"]] == ["E-2001"]
    assert result.rows_filtered == 1
    assert result.changed is True
    assert result.columns_redacted == []


def test_other_top_level_keys_are_preserved() -> None:
    result = project_result(
        _query_data(), _resource(), _grant(rows={"region": "$identity.region"}), _HR
    )

    assert result.data["count"] == 2


def test_list_valued_predicate_matches_any_member() -> None:
    result = project_result(_query_data(), _resource(), _grant(rows={"region": ["PL", "DE"]}), _HR)

    assert len(result.data["rows"]) == 2
    assert result.rows_filtered == 0
    assert result.changed is False


def test_list_predicate_supports_identity_substitution() -> None:
    result = project_result(
        _query_data(), _resource(), _grant(rows={"region": ["$identity.region", "FR"]}), _HR
    )

    assert [row["id"] for row in result.data["rows"]] == ["E-2001"]


def test_literal_predicate_value() -> None:
    result = project_result(_query_data(), _resource(), _grant(rows={"region": "DE"}), _HR)

    assert [row["id"] for row in result.data["rows"]] == ["E-2101"]


def test_sub_and_role_attributes_are_substituted() -> None:
    data = {"rows": [{"owner": "marek", "role": "hr"}, {"owner": "x", "role": "finance"}]}

    by_sub = project_result(data, _resource(), _grant(rows={"owner": "$identity.sub"}), _HR)
    by_role = project_result(data, _resource(), _grant(rows={"role": "$identity.role"}), _HR)

    assert [row["owner"] for row in by_sub.data["rows"]] == ["marek"]
    assert [row["owner"] for row in by_role.data["rows"]] == ["marek"]


def test_location_attribute_is_substituted() -> None:
    hr = make_identity(role=Role.hr, location="Krakow")
    data = {"rows": [{"site": "Krakow"}, {"site": "Berlin"}]}

    result = project_result(data, _resource(), _grant(rows={"site": "$identity.location"}), hr)

    assert result.data["rows"] == [{"site": "Krakow"}]


def test_record_missing_predicate_attribute_does_not_match() -> None:
    data = {"rows": [{"id": "a"}, {"id": "b", "region": "PL"}]}

    result = project_result(data, _resource(), _grant(rows={"region": "$identity.region"}), _HR)

    assert result.data["rows"] == [{"id": "b", "region": "PL"}]
    assert result.rows_filtered == 1


def test_unknown_identity_attribute_matches_nothing() -> None:
    result = project_result(
        _query_data(), _resource(), _grant(rows={"region": "$identity.nope"}), _HR
    )

    assert result.data["rows"] == []
    assert result.rows_filtered == 2


def test_column_deny_removes_columns() -> None:
    result = project_result(_query_data(), _resource(), _grant(deny=["salary"]), _HR)

    assert all("salary" not in row for row in result.data["rows"])
    assert result.columns_redacted == ["salary"]
    assert result.rows_filtered == 0
    assert result.changed is True


def test_column_allow_keeps_only_listed_columns() -> None:
    result = project_result(_query_data(), _resource(), _grant(allow=["id"]), _HR)

    assert result.data["rows"] == [{"id": "E-2001"}, {"id": "E-2101"}]
    assert result.columns_redacted == ["region", "salary"]


def test_deny_is_applied_after_allow() -> None:
    result = project_result(
        _query_data(), _resource(), _grant(allow=["id", "salary"], deny=["salary"]), _HR
    )

    assert result.data["rows"] == [{"id": "E-2001"}, {"id": "E-2101"}]
    assert result.columns_redacted == ["region", "salary"]


def test_empty_allow_list_removes_every_column() -> None:
    result = project_result(_query_data(), _resource(), _grant(allow=[]), _HR)

    assert result.data["rows"] == [{}, {}]


def test_redacted_columns_are_only_those_actually_removed() -> None:
    result = project_result(_query_data(), _resource(), _grant(deny=["salary", "ssn"]), _HR)

    assert result.columns_redacted == ["salary"]


def test_columns_of_filtered_rows_are_not_reported() -> None:
    data = {"rows": [{"id": "a", "region": "PL"}, {"id": "b", "region": "DE", "salary": 1}]}

    result = project_result(data, _resource(), _grant(rows={"region": "PL"}, deny=["salary"]), _HR)

    assert result.columns_redacted == []
    assert result.rows_filtered == 1


def test_flat_record_is_projected_by_column() -> None:
    record = {"id": "E-1042", "region": "PL", "salary": 9000, "name": "A"}

    result = project_result(record, _resource(records=None), _grant(deny=["salary"]), _HR)

    assert result.data == {"id": "E-1042", "region": "PL", "name": "A"}
    assert result.columns_redacted == ["salary"]
    assert result.rows_filtered == 0


def test_flat_record_outside_row_scope_is_replaced() -> None:
    record = {"id": "E-9", "region": "DE", "salary": 9000}

    result = project_result(
        record, _resource(records=None), _grant(rows={"region": "$identity.region"}), _HR
    )

    assert result.data == {"redacted": "outside row scope"}
    assert result.rows_filtered == 1
    assert result.columns_redacted == []
    assert result.changed is True


def test_flat_record_in_scope_without_sensitive_columns_is_unchanged() -> None:
    record = {"id": "E-1042", "region": "PL", "name": "A"}

    result = project_result(
        record,
        _resource(records=None),
        _grant(rows={"region": "$identity.region"}, deny=["salary"]),
        _HR,
    )

    assert result.data == record
    assert result.changed is False
    assert result.columns_redacted == []
    assert result.rows_filtered == 0


def test_unrestricted_grant_is_a_no_op() -> None:
    data = _query_data()

    result = project_result(data, _resource(), ResourceGrant(), _HR)

    assert result.data == data
    assert result.changed is False


def test_non_list_records_key_leaves_data_unchanged() -> None:
    data = {"rows": "not a list", "other": 1}

    result = project_result(data, _resource(), _grant(deny=["salary"]), _HR)

    assert result.data == data
    assert result.changed is False


def test_missing_records_key_leaves_data_unchanged() -> None:
    data = {"other": 1}

    result = project_result(data, _resource(), _grant(deny=["salary"]), _HR)

    assert result.data == data
    assert result.changed is False


def test_non_dict_payload_is_unchanged() -> None:
    result = project_result([1, 2], _resource(records=None), _grant(deny=["salary"]), _HR)

    assert result.data == [1, 2]
    assert result.changed is False


def test_input_is_never_mutated() -> None:
    data = _query_data()
    snapshot = copy.deepcopy(data)

    project_result(
        data, _resource(), _grant(rows={"region": "$identity.region"}, deny=["salary"]), _HR
    )

    assert data == snapshot

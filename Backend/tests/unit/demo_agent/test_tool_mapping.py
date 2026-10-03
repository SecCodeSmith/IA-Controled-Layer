from __future__ import annotations

import pytest

from demo_agent.schemas import ToolDescriptor
from demo_agent.tool_mapping import (
    parse_function_name,
    to_openai_function_name,
    to_openai_tools,
    tool_descriptor_to_openai_function,
)


def test_round_trip_simple_server() -> None:
    name = to_openai_function_name("github", "list_branches")
    assert name == "github__list_branches"
    assert parse_function_name(name) == ("github", "list_branches")


def test_round_trip_hyphenated_server() -> None:
    name = to_openai_function_name("logs-db", "query")
    assert name == "logs-db__query"
    assert parse_function_name(name) == ("logs-db", "query")


def test_round_trip_hyphenated_server_with_underscored_tool() -> None:
    name = to_openai_function_name("hr-db", "find_approver")
    assert name == "hr-db__find_approver"
    assert parse_function_name(name) == ("hr-db", "find_approver")


def test_round_trip_eu_customers_server() -> None:
    name = to_openai_function_name("eu-customers", "read")
    assert name == "eu-customers__read"
    assert parse_function_name(name) == ("eu-customers", "read")


def test_parse_function_name_rejects_missing_separator() -> None:
    with pytest.raises(ValueError):
        parse_function_name("not_a_qualified_name")


def test_parse_function_name_rejects_empty_server_or_tool() -> None:
    with pytest.raises(ValueError):
        parse_function_name("__query")
    with pytest.raises(ValueError):
        parse_function_name("logs-db__")


def test_tool_descriptor_to_openai_function_shape() -> None:
    descriptor = ToolDescriptor(
        server="logs-db",
        name="query",
        qualified_name="logs-db.query",
        description="Query recent log lines.",
        input_schema={"type": "object", "properties": {"service": {"type": "string"}}},
        tags=[],
    )

    spec = tool_descriptor_to_openai_function(descriptor)

    assert spec == {
        "type": "function",
        "function": {
            "name": "logs-db__query",
            "description": "Query recent log lines.",
            "parameters": {"type": "object", "properties": {"service": {"type": "string"}}},
        },
    }


def test_to_openai_tools_maps_all_descriptors_in_order() -> None:
    descriptors = [
        ToolDescriptor(
            server="github",
            name="get_readme",
            qualified_name="github.get_readme",
            description="Get a README.",
            input_schema={},
        ),
        ToolDescriptor(
            server="hr-db",
            name="get_employee",
            qualified_name="hr-db.get_employee",
            description="Get an employee record.",
            input_schema={},
        ),
    ]

    specs = to_openai_tools(descriptors)

    assert [spec["function"]["name"] for spec in specs] == [
        "github__get_readme",
        "hr-db__get_employee",
    ]

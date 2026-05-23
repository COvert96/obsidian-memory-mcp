from __future__ import annotations

import json
from pathlib import Path

from obsidian_memory_mcp.contracts import TOOL_CONTRACTS
from obsidian_memory_mcp.errors import ErrorCode
from obsidian_memory_mcp.validation import validate_tool_payload


DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"


def _load_json(relative_path: str) -> object:
    return json.loads((DOCS_DIR / relative_path).read_text(encoding="utf-8"))


def test_machine_readable_tool_spec_is_complete_and_schema_valid() -> None:
    spec = _load_json("tool-specifications.json")
    tools = spec["tools"]

    assert {tool["name"] for tool in tools} == set(TOOL_CONTRACTS)

    for tool in tools:
        tool_name = tool["name"]
        validate_tool_payload(tool_name, tool["example_request"], schema_kind="request")
        validate_tool_payload(tool_name, tool["example_response"], schema_kind="response")

        documented_codes = {scenario["code"] for scenario in tool["error_scenarios"]}
        allowed_codes = {code.value for code in TOOL_CONTRACTS[tool_name].possible_errors}
        assert documented_codes <= allowed_codes

        for scenario in tool["error_scenarios"]:
            error = scenario["example_response"]
            assert {"code", "message", "details"} <= set(error)
            assert ErrorCode(error["code"]).value == error["code"]


def test_machine_readable_spec_includes_unexpected_db_failure_examples() -> None:
    spec = _load_json("tool-specifications.json")
    has_unexpected_database_scenario = False

    for tool in spec["tools"]:
        for scenario in tool["error_scenarios"]:
            when_text = scenario["when"].lower()
            if (
                scenario["code"] == ErrorCode.ERR_INTERNAL.value
                and "database" in when_text
                and ("connection" in when_text or "connectivity" in when_text)
            ):
                has_unexpected_database_scenario = True

    assert has_unexpected_database_scenario


def test_mcp_inspector_examples_are_schema_executable() -> None:
    examples = _load_json("mcp-inspector-examples.json")

    for example in examples:
        request = example["request"]
        assert request["method"] == "tools/call"

        tool_name = request["params"]["name"]
        arguments = request["params"]["arguments"]
        validate_tool_payload(tool_name, arguments, schema_kind="request")

        expected = example["expected"]
        if expected["kind"] == "success":
            validate_tool_payload(tool_name, expected["result"], schema_kind="response")
        else:
            error = expected["error"]
            assert {"code", "message", "details"} <= set(error)
            assert ErrorCode(error["code"]) in TOOL_CONTRACTS[tool_name].possible_errors

from __future__ import annotations

import asyncio

import pytest
import tiktoken

from obsidian_memory_mcp.contracts import TOOL_CONTRACTS
from obsidian_memory_mcp.errors import ErrorCode, ERROR_CATALOG, TOOL_ERROR_CODES, build_error
from obsidian_memory_mcp.tokens import estimate_tokens
from obsidian_memory_mcp.validation import (
    ValidationError,
    load_tool_schema,
    validate_tool_handler,
    validate_tool_payload,
)


EXPECTED_TOOL_NAMES = {
    "approve_proposal",
    "get_context_pack",
    "list_proposals",
    "propose_memory_update",
    "read_note",
    "read_section",
    "search_notes",
}


def test_all_phase_zero_tools_are_registered() -> None:
    assert set(TOOL_CONTRACTS) == EXPECTED_TOOL_NAMES


def test_tool_error_codes_match_contracts() -> None:
    assert set(TOOL_ERROR_CODES) == set(TOOL_CONTRACTS)
    for tool_name, contract in TOOL_CONTRACTS.items():
        assert TOOL_ERROR_CODES[tool_name] == contract.possible_errors


@pytest.mark.parametrize("tool_name", sorted(EXPECTED_TOOL_NAMES))
def test_examples_validate_against_request_and_response_schemas(tool_name: str) -> None:
    contract = TOOL_CONTRACTS[tool_name]

    validate_tool_payload(tool_name, contract.example_request, schema_kind="request")
    validate_tool_payload(tool_name, contract.example_response, schema_kind="response")


def test_validation_reports_missing_required_fields_with_actionable_details() -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_tool_payload("read_note", {"project": "occlave"}, schema_kind="request")

    error = exc_info.value.error
    assert error.code is ErrorCode.ERR_INVALID_REQUEST
    assert "note_path" in error.message
    assert error.details["field_path"] == "note_path"
    assert "required" in error.details["validator"]
    assert "Provide the missing required field" in error.details["suggestion"]


def test_validation_rejects_wrong_types_and_out_of_range_values() -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_tool_payload(
            "search_notes",
            {
                "project": "occlave",
                "query": "compliance",
                "limit": 0,
                "tags": "eu-ai-act",
            },
            schema_kind="request",
        )

    error = exc_info.value.error
    assert error.code is ErrorCode.ERR_INVALID_REQUEST
    assert error.details["field_path"] in {"limit", "tags"}
    assert error.details["suggestion"]


@pytest.mark.parametrize("tool_name", sorted(EXPECTED_TOOL_NAMES))
def test_validation_rejects_invalid_project_identifiers(tool_name: str) -> None:
    payload = dict(TOOL_CONTRACTS[tool_name].example_request)
    payload["project"] = "bad project id"

    with pytest.raises(ValidationError) as exc_info:
        validate_tool_payload(tool_name, payload, schema_kind="request")

    error = exc_info.value.error
    assert error.code is ErrorCode.ERR_INVALID_REQUEST
    assert error.details["field_path"] == "project"
    assert error.details["validator"] == "pattern"


def test_validation_rejects_invalid_proposal_identifier() -> None:
    payload = dict(TOOL_CONTRACTS["approve_proposal"].example_request)
    payload["proposal_id"] = "not-a-uuid"

    with pytest.raises(ValidationError) as exc_info:
        validate_tool_payload("approve_proposal", payload, schema_kind="request")

    error = exc_info.value.error
    assert error.code is ErrorCode.ERR_INVALID_REQUEST
    assert error.details["field_path"] == "proposal_id"
    assert error.details["validator"] == "pattern"


def test_validation_decorator_short_circuits_invalid_requests() -> None:
    calls: list[dict[str, object]] = []

    @validate_tool_handler("approve_proposal")
    def handler(payload: dict[str, object]) -> dict[str, object]:
        calls.append(payload)
        return {
            "project": payload["project"],
            "proposal_id": payload["proposal_id"],
            "file_path": "Memory/example.md",
            "operation": "update",
            "status": "applied",
            "written_at": "2026-05-23T10:15:00Z",
            "file_size_bytes": 128,
        }

    with pytest.raises(ValidationError):
        handler({"project": "occlave"})

    assert calls == []


def test_validation_decorator_supports_async_handlers() -> None:
    contract = TOOL_CONTRACTS["approve_proposal"]

    @validate_tool_handler("approve_proposal")
    async def handler(payload: dict[str, object]) -> dict[str, object]:
        assert payload == contract.example_request
        return contract.example_response

    response = asyncio.run(handler(contract.example_request))

    assert response == contract.example_response


def test_proposal_id_schemas_accept_uuid_v7() -> None:
    response = dict(TOOL_CONTRACTS["approve_proposal"].example_response)
    response["proposal_id"] = "018f2f40-85f0-7cc8-9d09-6f75ef4c7b22"

    validate_tool_payload("approve_proposal", response, schema_kind="response")


def test_missing_tool_schema_is_reported_as_internal_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        load_tool_schema("missing_tool")

    assert exc_info.value.error.code is ErrorCode.ERR_INTERNAL


def test_error_catalog_includes_phase_zero_metadata() -> None:
    assert ERROR_CATALOG[ErrorCode.ERR_INVALID_PROJECT].http_status == 404
    assert ERROR_CATALOG[ErrorCode.ERR_MISSING_FILE].recovery_suggestion
    assert ERROR_CATALOG[ErrorCode.ERR_SECTION_NOT_FOUND].message_template
    assert ERROR_CATALOG[ErrorCode.ERR_GUARDRAIL_VIOLATION].recovery_suggestion
    assert ERROR_CATALOG[ErrorCode.ERR_STALE_PROPOSAL].http_status == 409
    assert ERROR_CATALOG[ErrorCode.ERR_CONTEXT_EXCEEDS_BUDGET].http_status == 422


def test_error_template_placeholders_are_formatted_from_details() -> None:
    error = build_error(
        ErrorCode.ERR_MISSING_FILE,
        details={"file_path": "wiki/missing.md"},
    )

    assert error.message == "File 'wiki/missing.md' does not exist in the project vault."


def test_known_token_examples_are_deterministic() -> None:
    five_tokens = " ".join(["x"] * 5)
    one_hundred_tokens = " ".join(["x"] * 100)
    one_thousand_tokens = " ".join(["x"] * 1000)

    assert estimate_tokens(five_tokens) == 5
    assert estimate_tokens(one_hundred_tokens) == 100
    assert estimate_tokens(one_thousand_tokens) == 1000
    assert estimate_tokens("# Heading\n\n- bullet\n[[Link]]") == estimate_tokens(
        "# Heading\r\n\r\n- bullet\r\n[[Link]]"
    )


def test_estimate_tokens_matches_tiktoken_gpt4_encoder() -> None:
    encoder = tiktoken.encoding_for_model("gpt-4")
    text = "# Title\n\n- alpha\n- beta\n\n[[Link]]"
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    assert estimate_tokens(text) == len(encoder.encode(normalized, disallowed_special=()))


def test_empty_string_returns_zero_tokens() -> None:
    assert estimate_tokens("") == 0

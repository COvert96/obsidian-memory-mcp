"""Tests for tool contracts and the error catalog."""

from __future__ import annotations

from obsidian_memory_mcp.contracts import TOOL_CONTRACTS, TOOL_ERROR_CODES
from obsidian_memory_mcp.errors import ERROR_CATALOG, ErrorCode, build_error


EXPECTED_TOOL_NAMES = {
    "approve_proposal",
    "get_context_pack",
    "list_context_packs",
    "list_proposals",
    "propose_memory_update",
    "read_note",
    "read_section",
    "reject_proposal",
    "search_notes",
    "update_memory",
    "update_note",
    "write_memory",
    "write_note",
}


# ---------------------------------------------------------------------------
# Contract completeness
# ---------------------------------------------------------------------------


def test_all_expected_tools_are_registered() -> None:
    assert set(TOOL_CONTRACTS) == EXPECTED_TOOL_NAMES


def test_every_contract_has_a_non_empty_description() -> None:
    for name, contract in TOOL_CONTRACTS.items():
        assert contract.description, f"Tool '{name}' has an empty description."


def test_every_contract_declares_at_least_one_error_code() -> None:
    for name, contract in TOOL_CONTRACTS.items():
        assert contract.possible_errors, f"Tool '{name}' declares no possible errors."


def test_tool_error_codes_matches_contract_possible_errors() -> None:
    """TOOL_ERROR_CODES is derived from TOOL_CONTRACTS; verify the derivation is consistent."""
    for name, contract in TOOL_CONTRACTS.items():
        assert TOOL_ERROR_CODES[name] == contract.possible_errors


def test_read_section_contract_documents_context_prefix() -> None:
    response = TOOL_CONTRACTS["read_section"].example_response

    assert "context_prefix" in response
    assert "context_lines" not in response
    assert str(response["content"]).startswith("## ")


def test_search_notes_contract_documents_heading_level_and_path_filters() -> None:
    request = TOOL_CONTRACTS["search_notes"].example_request
    result = TOOL_CONTRACTS["search_notes"].example_response["results"][0]

    assert isinstance(request["paths"], list)
    assert "exclude_paths" in request
    assert "heading_level" in result


def test_list_context_packs_contract_documents_metadata_fields() -> None:
    response = TOOL_CONTRACTS["list_context_packs"].example_response

    assert response["returned_count"] >= 1
    first_pack = response["context_packs"][0]
    assert "pack_name" in first_pack
    assert "token_budget" in first_pack
    assert "description" in first_pack


def test_proposal_contracts_use_consistent_ids_and_error_codes() -> None:
    list_item = TOOL_CONTRACTS["list_proposals"].example_response["proposals"][0]
    approve_errors = TOOL_CONTRACTS["approve_proposal"].possible_errors

    assert "proposal_id" in list_item
    assert "id" not in list_item
    assert ErrorCode.ERR_MISSING_FILE not in approve_errors


def test_propose_memory_update_contract_declares_memory_scope() -> None:
    contract = TOOL_CONTRACTS["propose_memory_update"]
    file_path = contract.example_request["file_path"]

    assert "Memory/" in contract.description
    assert isinstance(file_path, str)
    assert file_path.startswith("Memory/")


# ---------------------------------------------------------------------------
# Error catalog
# ---------------------------------------------------------------------------


def test_error_catalog_covers_all_error_codes() -> None:
    for code in ErrorCode:
        assert code in ERROR_CATALOG, (
            f"ErrorCode {code!r} is missing from ERROR_CATALOG."
        )


def test_error_catalog_entries_have_non_empty_recovery_suggestions() -> None:
    for code, definition in ERROR_CATALOG.items():
        assert definition.recovery_suggestion, (
            f"{code!r} has an empty recovery_suggestion."
        )


def test_error_template_placeholders_format_from_details() -> None:
    error = build_error(
        ErrorCode.ERR_MISSING_FILE,
        details={"file_path": "wiki/missing.md"},
    )
    assert (
        error.message == "File 'wiki/missing.md' does not exist in the project vault."
    )


def test_missing_placeholder_key_is_left_unchanged() -> None:
    # If a template key is absent from details, the placeholder should survive verbatim.
    error = build_error(ErrorCode.ERR_MISSING_FILE, details={})
    assert "{file_path}" in error.message
